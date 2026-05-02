#!/usr/bin/env python3
"""
substack_draft_email.py — Emails a Substack-ready daily draft to one recipient.

Pulls today's NA picks + yesterday's accuracy + 30-day rolling calibration,
selects 2-3 featured races with reasoning blurbs from the Redis-cached full
analysis, and renders both an HTML body (paste-safe semantic HTML for
Substack's rich editor) and a markdown mirror (for its markdown mode).

Designed to run right after morning_line_email.py in the same cron chain.

Usage:
    cd backend
    railway run python scripts/substack_draft_email.py
    railway run python scripts/substack_draft_email.py --date 2026-05-02
    railway run python scripts/substack_draft_email.py --dry-run
"""
import argparse
import asyncio
import datetime
import os
import sys
from itertools import groupby

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def _norm(name: str) -> str:
    return (name or "").lower().strip().replace("'", "").replace("-", " ")


def _twelve_hour_et(post_et: str) -> str:
    """'14:30' -> '2:30 PM ET'. Empty/malformed -> '—'."""
    if not post_et or len(post_et) < 4 or ":" not in post_et:
        return "—"
    try:
        h, m = post_et.split(":")
        h_et, m_int = int(h) % 24, int(m)
    except ValueError:
        return post_et
    suffix = "AM" if h_et < 12 else "PM"
    return f"{h_et % 12 or 12}:{m_int:02d} {suffix} ET"


async def _fetch_racecards_and_lookup(target_date: datetime.date) -> tuple[dict, dict]:
    """Returns ({race_id: race_dict}, {race_id: {norm_name: program_num}}).
    Falls back to ({}, {}) on fetch failure so the email still renders."""
    today = datetime.date.today()
    day_param = (
        "today" if target_date == today
        else "tomorrow" if target_date == today + datetime.timedelta(days=1)
        else target_date.isoformat()
    )
    try:
        from app.services.racing_api import get_na_racecards_full
        data = await get_na_racecards_full(day_param)
    except Exception as e:
        print(f"  Racecard fetch failed ({e}) — proceeding without enrichment")
        return {}, {}

    by_id: dict[str, dict] = {}
    runner_lookup: dict[str, dict[str, str]] = {}
    for race in data.get("racecards", []) or []:
        race_id = race.get("race_id") or race.get("id") or ""
        if not race_id:
            continue
        by_id[race_id] = race
        runners = {}
        for r in race.get("runners", []):
            name = r.get("horse") or r.get("horse_name") or ""
            num = r.get("number") or r.get("program_number") or r.get("cloth_number") or ""
            if name and num:
                runners[_norm(name)] = str(num).lstrip("#").strip()
        if runners:
            runner_lookup[race_id] = runners
    return by_id, runner_lookup


async def _select_featured(predictions, race_data_by_id, calibration, want=3) -> list[dict]:
    """Pick the day's most compelling races. Strategy:

    1. For every prediction, try to load the cached full analysis (Redis)
       using the same fingerprint nightly_predict_all wrote with.
    2. Prefer high-confidence picks; rank ties by track historical win rate.
    3. Return up to `want` featured items.

    Best-effort — silently skips races without cache hits.
    """
    from app.core.cache import cache_get
    from app.services.secretariat import compute_input_fingerprint

    track_wr = (calibration.win_rate_by_track or {}) if calibration else {}

    candidates = []
    for p in predictions:
        race = race_data_by_id.get(p.race_id)
        if not race:
            continue
        fp = compute_input_fingerprint(race)
        cache_key = f"ai_analysis:{p.race_id}:medium:{fp}"
        analysis = await cache_get(cache_key)
        if not analysis:
            continue
        blurb = (
            analysis.get("overall_summary_beginner")
            or analysis.get("overall_summary")
            or ""
        ).strip()
        if not blurb:
            continue
        confidence = (analysis.get("confidence") or "").lower()
        track_data = track_wr.get(p.track_code) or {}
        candidates.append({
            "prediction": p,
            "race_data": race,
            "analysis": analysis,
            "blurb": blurb,
            "confidence": confidence,
            "_rank_conf": {"high": 3, "medium": 2, "low": 1}.get(confidence, 0),
            "_rank_track_wr": float(track_data.get("win_rate", 0) or 0),
        })

    candidates.sort(key=lambda c: (c["_rank_conf"], c["_rank_track_wr"]), reverse=True)
    return candidates[:want]


def _scoreboard(yesterday_report, calibration) -> tuple[str, str]:
    """Two-line scoreboard. Returns (html, markdown)."""
    html_lines, md_lines = [], []
    if yesterday_report and yesterday_report.races_analyzed:
        wins, itm, total = (
            yesterday_report.top_pick_wins,
            yesterday_report.in_the_money,
            yesterday_report.races_analyzed,
        )
        html_lines.append(
            f"<strong>Yesterday:</strong> {wins} wins from {total} top picks "
            f"({wins/total:.1%}) · {itm} in the money ({itm/total:.1%})"
        )
        md_lines.append(
            f"**Yesterday:** {wins} wins from {total} top picks "
            f"({wins/total:.1%}) · {itm} in the money ({itm/total:.1%})"
        )
    if calibration and calibration.sample_size:
        html_lines.append(
            f"<strong>30-day rolling:</strong> "
            f"{calibration.rolling_win_rate:.1%} top-pick win rate · "
            f"{calibration.sample_size:,} races"
        )
        md_lines.append(
            f"**30-day rolling:** {calibration.rolling_win_rate:.1%} top-pick win rate · "
            f"{calibration.sample_size:,} races"
        )
    if not html_lines:
        return "", ""
    html = "<blockquote>" + "<br>".join(html_lines) + "</blockquote>"
    md = "\n".join(f"> {line}" for line in md_lines)
    return html, md


def _render(predictions, yesterday_report, calibration, runner_lookup, race_data_by_id, featured, target_date) -> dict:
    """Builds {subject, html, text, markdown}. The HTML body is what gets
    pasted into Substack's rich editor; the markdown mirror is for its
    markdown-mode editor. Both are designed to look like a published piece,
    not a debug dump."""
    from app.services.secretariat import TRACK_NAMES

    long_date = target_date.strftime("%A, %B %d, %Y")
    short_date = target_date.strftime("%a %b %-d")

    predictions = sorted(
        predictions,
        key=lambda p: (
            p.track_code or "ZZZ",
            getattr(p, "post_time_et", None) or "99:99",
            p.race_name or "",
        ),
    )
    track_groups = [(t, list(items)) for t, items in groupby(predictions, key=lambda p: p.track_code or "?")]
    total_picks = len(predictions)
    total_tracks = len(track_groups)

    def _track_name(code: str) -> str:
        return TRACK_NAMES.get((code or "").upper(), code or "Unknown track")

    def _label(race_id: str, horse: str | None, fallback_num: str | None = None) -> str:
        if not horse:
            return "—"
        num = runner_lookup.get(race_id, {}).get(_norm(horse))
        if not num and fallback_num:
            num = fallback_num.lstrip("#").strip() or None
        return f"#{num} {horse}" if num else horse

    def _race_descriptor(p) -> str:
        bits = []
        race_label = p.race_name or p.race_id or ""
        if race_label:
            bits.append(race_label)
        type_part = " ".join(b for b in [p.race_type, p.surface] if b)
        if type_part:
            bits.append(type_part)
        return " · ".join(bits) or "—"

    score_html, score_md = _scoreboard(yesterday_report, calibration)

    # ── HTML body (Substack rich-editor paste target) ──────────────────────────
    html: list[str] = []
    html.append("<h1>Secretariat's Morning Line</h1>")
    html.append(
        f"<h3><em>{long_date} · {total_picks} picks across {total_tracks} tracks</em></h3>"
    )
    if score_html:
        html.append(score_html)

    if featured:
        html.append("<hr>")
        html.append("<h2>Featured plays</h2>")
        html.append(
            "<p><em>The races where Secretariat sees the strongest edge today. "
            "Reasoning is the model's, written for non-handicappers.</em></p>"
        )
        for f in featured:
            p = f["prediction"]
            track_full = _track_name(p.track_code)
            post = _twelve_hour_et(p.post_time_et or "")
            win = _label(p.race_id, p.predicted_first, p.predicted_first_num)
            place = _label(p.race_id, p.predicted_second)
            show = _label(p.race_id, p.predicted_third)
            type_line = " · ".join(b for b in [p.race_type, p.surface, post] if b)
            conf_badge = f" <em>(confidence: {f['confidence']})</em>" if f["confidence"] else ""
            html.append(f"<h3>{track_full} — {p.race_name or p.race_id}{conf_badge}</h3>")
            html.append(f"<p><strong>WIN: {win}</strong><br><small>{type_line}</small></p>")
            html.append(f"<blockquote>{f['blurb']}</blockquote>")
            html.append(f"<p><strong>Backup picks:</strong> PLACE {place} · SHOW {show}</p>")

    html.append("<hr>")
    html.append("<h2>The full card</h2>")
    for track, items in track_groups:
        track_full = _track_name(track)
        html.append(f"<h3>{track_full}</h3>")
        html.append(
            "<table><thead><tr>"
            "<th>Post (ET)</th><th>Race</th>"
            "<th>Win</th><th>Place</th><th>Show</th>"
            "</tr></thead><tbody>"
        )
        for p in items:
            html.append(
                "<tr>"
                f"<td>{_twelve_hour_et(p.post_time_et or '')}</td>"
                f"<td>{_race_descriptor(p)}</td>"
                f"<td><strong>{_label(p.race_id, p.predicted_first, p.predicted_first_num)}</strong></td>"
                f"<td>{_label(p.race_id, p.predicted_second)}</td>"
                f"<td>{_label(p.race_id, p.predicted_third)}</td>"
                "</tr>"
            )
        html.append("</tbody></table>")

    html.append("<hr>")
    html.append(
        "<p><em>Secretariat is GateSmart's AI handicapper. Every pick above comes with full "
        "contender breakdowns, fair odds, and confidence tiers inside the app — see the "
        "individual race page for the reasoning behind any horse on this card.</em></p>"
    )
    html.append(
        "<p><small>Informational only. Not betting advice. Past performance is not predictive.</small></p>"
    )
    html_body = "\n".join(html)

    # ── Markdown mirror (Substack markdown-mode paste target) ──────────────────
    md: list[str] = []
    md.append("# Secretariat's Morning Line")
    md.append(f"### *{long_date} · {total_picks} picks across {total_tracks} tracks*")
    if score_md:
        md.append(score_md)

    if featured:
        md.append("---")
        md.append("## Featured plays")
        md.append(
            "*The races where Secretariat sees the strongest edge today. "
            "Reasoning is the model's, written for non-handicappers.*"
        )
        for f in featured:
            p = f["prediction"]
            track_full = _track_name(p.track_code)
            post = _twelve_hour_et(p.post_time_et or "")
            win = _label(p.race_id, p.predicted_first, p.predicted_first_num)
            place = _label(p.race_id, p.predicted_second)
            show = _label(p.race_id, p.predicted_third)
            type_line = " · ".join(b for b in [p.race_type, p.surface, post] if b)
            conf_badge = f" *(confidence: {f['confidence']})*" if f["confidence"] else ""
            md.append(f"### {track_full} — {p.race_name or p.race_id}{conf_badge}")
            md.append(f"**WIN: {win}**  \n*{type_line}*")
            md.append(f"> {f['blurb']}")
            md.append(f"**Backup picks:** PLACE {place} · SHOW {show}")

    md.append("---")
    md.append("## The full card")
    for track, items in track_groups:
        track_full = _track_name(track)
        md.append(f"### {track_full}")
        md.append("| Post (ET) | Race | Win | Place | Show |")
        md.append("|---|---|---|---|---|")
        for p in items:
            md.append(
                f"| {_twelve_hour_et(p.post_time_et or '')} "
                f"| {_race_descriptor(p)} "
                f"| **{_label(p.race_id, p.predicted_first, p.predicted_first_num)}** "
                f"| {_label(p.race_id, p.predicted_second)} "
                f"| {_label(p.race_id, p.predicted_third)} |"
            )

    md.append("---")
    md.append(
        "*Secretariat is GateSmart's AI handicapper. Every pick above comes with full "
        "contender breakdowns, fair odds, and confidence tiers inside the app — see the "
        "individual race page for the reasoning behind any horse on this card.*"
    )
    md.append("*Informational only. Not betting advice. Past performance is not predictive.*")
    markdown_body = "\n\n".join(md)

    # ── Email envelope ─────────────────────────────────────────────────────────
    full_html = (
        f'<div style="font-family:Georgia,serif;max-width:760px;margin:auto;color:#1a1a1a">'
        f'  <p style="font-size:12px;color:#888;margin-bottom:16px">'
        f'    Substack draft for {long_date}. Copy the block below into a new Substack post '
        f'    (rich-editor preserves headings, lists, tables, and blockquotes). '
        f'    Markdown version follows below for the markdown-mode editor.'
        f'  </p>'
        f'  <div style="border:1px solid #ddd;padding:24px;background:#fff;line-height:1.55">'
        f'  {html_body}'
        f'  </div>'
        f'  <p style="font-size:12px;color:#888;margin:24px 0 8px">'
        f'    — Markdown version (paste into Substack\'s markdown mode if preferred) —'
        f'  </p>'
        f'  <pre style="background:#f6f6f6;padding:16px;border:1px solid #ddd;'
        f'white-space:pre-wrap;font-size:12px;line-height:1.5">{markdown_body}</pre>'
        f'</div>'
    )

    plain_text = (
        f"Substack draft for {long_date}\n"
        f"{total_picks} picks across {total_tracks} tracks\n\n"
        f"Markdown version (paste into Substack):\n\n"
        f"{markdown_body}\n"
    )

    subject = (
        f"Substack Draft — Secretariat Morning Line — {short_date} | "
        f"{total_picks} picks · {total_tracks} tracks"
    )

    return {
        "subject": subject,
        "html": full_html,
        "text": plain_text,
        "markdown": markdown_body,
    }


async def main(target_date: datetime.date, dry_run: bool):
    from app.core import database as _db
    from app.core.config import settings
    from app.models.accuracy import (
        RacePrediction, DailyAccuracyReport, SecretariatCalibration,
    )
    from app.services.email_service import send_daily_report
    from sqlalchemy import select, or_, text as _text

    await _db.init_db()

    # Backfill columns added after initial table creation (mirrors morning_line_email).
    async with _db._engine.begin() as _conn:
        for stmt in [
            "ALTER TABLE daily_accuracy_reports ADD COLUMN IF NOT EXISTS place_picks_correct INTEGER DEFAULT 0",
            "ALTER TABLE daily_accuracy_reports ADD COLUMN IF NOT EXISTS show_picks_correct INTEGER DEFAULT 0",
            "ALTER TABLE daily_accuracy_reports ADD COLUMN IF NOT EXISTS place_rate FLOAT DEFAULT 0.0",
            "ALTER TABLE daily_accuracy_reports ADD COLUMN IF NOT EXISTS show_rate FLOAT DEFAULT 0.0",
            "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS lessons JSONB",
            "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS win_rate_by_track_type JSONB",
            "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS win_rate_by_track_surface JSONB",
            "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS win_rate_by_surface JSONB",
            "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS weak_spots JSONB",
            "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS strong_spots JSONB",
            "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS notes TEXT",
        ]:
            await _conn.execute(_text(stmt))

    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_date == target_date,
                or_(RacePrediction.region == "na", RacePrediction.region == None),  # noqa: E711
                RacePrediction.user_id == None,  # noqa: E711
                RacePrediction.analysis_mode == "auto_daily",
            )
        )
        predictions = list(result.scalars().all())

        yesterday = target_date - datetime.timedelta(days=1)
        yesterday_report = (await db.execute(
            select(DailyAccuracyReport).where(DailyAccuracyReport.report_date == yesterday)
        )).scalar_one_or_none()

        calibration = await db.get(SecretariatCalibration, 1)

    print(f"\n[substack_draft_email] Date: {target_date} | Picks: {len(predictions)} | dry_run={dry_run}")

    if not predictions:
        print("No predictions for today — exiting (did nightly_predict_all run?).")
        return

    race_data_by_id, runner_lookup = await _fetch_racecards_and_lookup(target_date)
    print(f"  Racecards fetched: {len(race_data_by_id)} | runner lookups: {len(runner_lookup)}")
    print(f"  Yesterday's report: {'found' if yesterday_report else 'missing'}")
    print(f"  Calibration sample: {calibration.sample_size if calibration else 0} races")

    featured = await _select_featured(predictions, race_data_by_id, calibration, want=3)
    print(f"  Featured races selected: {len(featured)}")

    email = _render(
        predictions, yesterday_report, calibration, runner_lookup,
        race_data_by_id, featured, target_date,
    )

    if dry_run:
        print(f"\nSubject: {email['subject']}\n")
        print("=" * 70)
        print("MARKDOWN PREVIEW")
        print("=" * 70)
        print(email["markdown"])
        return

    sent = await send_daily_report(
        subject=email["subject"],
        html_body=email["html"],
        text_body=email["text"],
        to_email=settings.SUBSTACK_DRAFT_EMAIL,
    )
    print(f"  send_daily_report → {sent}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (defaults to today)")
    parser.add_argument("--dry-run", action="store_true", help="Print draft instead of sending")
    args = parser.parse_args()

    target = (
        datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    )
    asyncio.run(main(target, args.dry_run))
