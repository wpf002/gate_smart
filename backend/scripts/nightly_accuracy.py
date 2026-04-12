#!/usr/bin/env python3
"""
nightly_accuracy.py — Fetches race results, settles predictions,
computes DailyAccuracyReport, and emails digest to wfoti71992@gmail.com.

Usage:
    cd backend
    python scripts/nightly_accuracy.py
    python scripts/nightly_accuracy.py --date 2026-04-11
    python scripts/nightly_accuracy.py --dry-run
"""
import argparse
import asyncio
import datetime
import os
import sys

# Ensure backend package is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def _norm(name: str) -> str:
    """Normalise a horse name for fuzzy comparison."""
    return (name or "").lower().strip().replace("'", "").replace("-", " ")


async def main(target_date: datetime.date, dry_run: bool):
    from app.core import database as _db
    from app.models.accuracy import RacePrediction, DailyAccuracyReport
    from sqlalchemy import select, update

    await _db.init_db()

    async with _db._AsyncSessionLocal() as db:
        # 1. Fetch all unsettled predictions for target_date
        result = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_date == target_date,
                RacePrediction.result_fetched == False,  # noqa: E712
            )
        )
        predictions = result.scalars().all()

    print(f"\n[nightly_accuracy] Date: {target_date} | Unsettled: {len(predictions)} | dry_run={dry_run}")

    if not predictions:
        print("Nothing to settle — exiting.")
        return

    # 2. Fetch results for each race from TheRacingAPI
    import httpx
    from app.core.config import settings

    settled = []
    for pred in predictions:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"https://api.theracingapi.com/v1/results/{pred.race_id}",
                    auth=(settings.RACING_API_USERNAME, settings.RACING_API_PASSWORD),
                )
            if resp.status_code != 200:
                print(f"  ✗ {pred.race_id}: API {resp.status_code}")
                continue

            data = resp.json()
            runners = data.get("runners", []) or data.get("results", [])

            def _finisher(pos: int):
                for r in runners:
                    p = r.get("position") or r.get("finish_position") or r.get("place")
                    try:
                        if int(str(p).strip()) == pos:
                            return r.get("horse") or r.get("horse_name", "")
                    except (ValueError, TypeError):
                        pass
                return None

            actual_first = _finisher(1)
            actual_second = _finisher(2)
            actual_third = _finisher(3)

            top_correct = bool(
                actual_first and pred.predicted_first and
                _norm(actual_first) == _norm(pred.predicted_first)
            )
            itm = bool(
                pred.predicted_first and actual_first and (
                    _norm(pred.predicted_first) == _norm(actual_first) or
                    _norm(pred.predicted_first) == _norm(actual_second or "") or
                    _norm(pred.predicted_first) == _norm(actual_third or "")
                )
            )

            settled.append({
                "id": pred.id,
                "race_id": pred.race_id,
                "race_name": pred.race_name,
                "predicted": pred.predicted_first,
                "actual": actual_first,
                "top_correct": top_correct,
                "itm": itm,
                "actual_first": actual_first,
                "actual_second": actual_second,
                "actual_third": actual_third,
            })
            result_icon = "✅" if top_correct else ("🔶" if itm else "❌")
            print(f"  {result_icon} {pred.race_name or pred.race_id}: predicted={pred.predicted_first}, actual={actual_first}")

        except Exception as e:
            print(f"  ✗ {pred.race_id}: {e}")

    if not settled:
        print("No results fetched — check API credentials.")
        return

    # 3. Update DB rows
    if not dry_run:
        async with _db._AsyncSessionLocal() as db:
            now = datetime.datetime.now(datetime.timezone.utc)
            for s in settled:
                await db.execute(
                    update(RacePrediction)
                    .where(RacePrediction.id == s["id"])
                    .values(
                        actual_first=s["actual_first"],
                        actual_second=s["actual_second"],
                        actual_third=s["actual_third"],
                        result_fetched=True,
                        top_pick_correct=s["top_correct"],
                        in_the_money=s["itm"],
                        settled_at=now,
                    )
                )
            await db.commit()

    # 4. Compute DailyAccuracyReport
    total = len(settled)
    wins = sum(1 for s in settled if s["top_correct"])
    itm_count = sum(1 for s in settled if s["itm"])
    win_rate = wins / total if total else 0.0
    itm_rate = itm_count / total if total else 0.0

    best = max((s for s in settled if s["top_correct"]), key=lambda s: 1, default=None)
    worst = max((s for s in settled if not s["top_correct"]), key=lambda s: 1, default=None)

    best_call = f"{best['race_name'] or best['race_id']}: {best['predicted']} won" if best else None
    worst_miss = f"{worst['race_name'] or worst['race_id']}: picked {worst['predicted']}, actual {worst['actual']}" if worst else None

    print(f"\n  Summary: {wins}/{total} wins ({win_rate:.1%}), {itm_count} ITM ({itm_rate:.1%})")

    # 5. Upsert DailyAccuracyReport
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    report_row = {
        "report_date": target_date,
        "total_races": total,
        "races_analyzed": total,
        "top_pick_wins": wins,
        "in_the_money": itm_count,
        "win_rate": win_rate,
        "itm_rate": itm_rate,
        "best_call": best_call,
        "worst_miss": worst_miss,
    }

    if not dry_run:
        async with _db._AsyncSessionLocal() as db:
            stmt = pg_insert(DailyAccuracyReport).values(**report_row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["report_date"],
                set_={k: v for k, v in report_row.items() if k != "report_date"},
            )
            await db.execute(stmt)
            await db.commit()

        # Reload report and predictions for email
        async with _db._AsyncSessionLocal() as db:
            rpt = await db.execute(
                select(DailyAccuracyReport).where(DailyAccuracyReport.report_date == target_date)
            )
            report_obj = rpt.scalar_one()

            preds_res = await db.execute(
                select(RacePrediction).where(
                    RacePrediction.race_date == target_date,
                    RacePrediction.result_fetched == True,  # noqa: E712
                )
            )
            preds_list = preds_res.scalars().all()
    else:
        # Build a fake report object for dry-run
        class _FakeReport:
            report_date = target_date
            races_analyzed = total
            top_pick_wins = wins
            in_the_money = itm_count
            win_rate = win_rate
            itm_rate = itm_rate
            best_call = best_call
            worst_miss = worst_miss
            by_track = None
            by_race_type = None

        class _FakePred:
            def __init__(self, s):
                self.race_id = s["race_id"]
                self.race_name = s["race_name"]
                self.track_code = None
                self.race_type = None
                self.predicted_first = s["predicted"]
                self.actual_first = s["actual"]
                self.top_pick_correct = s["top_correct"]
                self.in_the_money = s["itm"]

        report_obj = _FakeReport()
        preds_list = [_FakePred(s) for s in settled]

    # 6. Generate and send email
    from app.services.secretariat import generate_daily_email_report
    from app.services.email_service import send_daily_report

    print("\n[nightly_accuracy] Generating email via Claude…")
    email = await generate_daily_email_report(report_obj, preds_list)

    subject = email.get("subject", f"Secretariat Daily Report — {target_date}")
    text = email.get("text", "")
    html = email.get("html", "")

    print(f"\nSubject: {subject}")
    print(f"\nText preview:\n{text[:800]}")

    if dry_run:
        print("\n[DRY RUN] Email not sent.")
    else:
        sent = await send_daily_report(subject=subject, html_body=html, text_body=text)
        if sent:
            async with _db._AsyncSessionLocal() as db:
                await db.execute(
                    update(DailyAccuracyReport)
                    .where(DailyAccuracyReport.report_date == target_date)
                    .values(
                        email_sent=True,
                        email_sent_at=datetime.datetime.now(datetime.timezone.utc),
                    )
                )
                await db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nightly accuracy report")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (defaults to today)")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't write to DB or send email")
    args = parser.parse_args()

    if args.date:
        target = datetime.date.fromisoformat(args.date)
    else:
        target = datetime.date.today()

    asyncio.run(main(target, dry_run=args.dry_run))
