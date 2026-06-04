"""
Secretariat scorecard — measures whether the pick model is actually improving.

Prints weekly top-pick win% / ITM% cohorts plus a rolling summary, so the
post-learning-loop-fix window (>= 2026-05-28) can be evaluated cleanly against
the frozen baseline in docs/secretariat_baseline.md.

Usage:
    cd backend
    DATABASE_URL=postgresql://USER:PW@HOST:PORT/db python scripts/secretariat_scorecard.py
    # against prod, point DATABASE_URL at the Railway public proxy DSN

Reference points (thoroughbred racing):
    ~33% = post-time favorite win rate. Hitting 30-35% top-pick wins means
    picking winners about as well as the betting market. Below ~33% means the
    model is picking winners worse than blindly backing the favorite.
"""
import asyncio
import os
import sys

import asyncpg

# Loop went from silently-dead to live on this date (see project memory).
LOOP_FIX_DATE = "2026-05-28"
FAVORITE_BASELINE_PCT = 33.0  # post-time favorite win rate in thoroughbred racing
TARGET_PCT = 30.0


def _dsn() -> str:
    raw = os.getenv("DATABASE_URL")
    if not raw:
        sys.exit("Set DATABASE_URL (plain postgresql:// DSN, e.g. the Railway public proxy).")
    # asyncpg wants a plain postgresql:// scheme, not postgresql+asyncpg://
    return raw.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")


async def main() -> None:
    c = await asyncpg.connect(_dsn())
    try:
        print("=== Secretariat scorecard — weekly cohorts (races-weighted) ===")
        rows = await c.fetch(
            """
            SELECT date_trunc('week', report_date)::date AS wk,
                   SUM(total_races) AS races,
                   ROUND(100.0*SUM(top_pick_wins)/NULLIF(SUM(total_races),0), 1) AS win_pct,
                   ROUND(100.0*SUM(in_the_money)/NULLIF(SUM(total_races),0), 1) AS itm_pct
            FROM daily_accuracy_reports
            WHERE total_races > 0
            GROUP BY 1 ORDER BY 1
            """
        )
        print(f"  {'week_of':12} {'races':>6} {'win%':>6} {'itm%':>6}")
        for r in rows:
            flag = "  <- loop alive" if str(r["wk"]) >= LOOP_FIX_DATE else ""
            print(f"  {str(r['wk']):12} {r['races']:>6} {r['win_pct']:>6} {r['itm_pct']:>6}{flag}")

        print("\n=== before vs after loop-fix (%s) ===" % LOOP_FIX_DATE)
        for label, cond in [
            ("loop DEAD", f"report_date < '{LOOP_FIX_DATE}'"),
            ("loop ALIVE", f"report_date >= '{LOOP_FIX_DATE}'"),
        ]:
            r = await c.fetchrow(
                f"""
                SELECT SUM(total_races) AS races,
                       ROUND(100.0*SUM(top_pick_wins)/NULLIF(SUM(total_races),0), 1) AS win_pct,
                       ROUND(100.0*SUM(in_the_money)/NULLIF(SUM(total_races),0), 1) AS itm_pct
                FROM daily_accuracy_reports
                WHERE total_races > 0 AND {cond}
                """
            )
            print(f"  {label:11} races={r['races'] or 0:<6} win={r['win_pct']}%  itm={r['itm_pct']}%")

        cal = await c.fetchrow(
            "SELECT rolling_win_rate, sample_size, updated_at FROM secretariat_calibration ORDER BY id DESC LIMIT 1"
        )
        rolling = round((cal["rolling_win_rate"] or 0) * 100, 1)
        print("\n=== current rolling ===")
        print(f"  rolling_win_rate={rolling}%  sample={cal['sample_size']}  updated={cal['updated_at']:%Y-%m-%d %H:%M}")
        print(f"  favorite baseline ~{FAVORITE_BASELINE_PCT}%  |  target {TARGET_PCT}-35%  |  gap to target: {TARGET_PCT-rolling:+.1f} pts")

        # --- Favorite-agreement: the core learning diagnostic --------------
        # Where are the points leaking? If win% when picking the favorite is
        # high but Secretariat rarely picks it, the lever is "trust the market
        # more". If win% is low even on favorites, the handicapping itself is
        # off. (Populated from 2026-06-04 onward — odds capture start.)
        print("\n=== favorite-agreement (settled picks with market data) ===")
        rows = await c.fetch(
            """
            SELECT top_pick_is_favorite AS is_fav,
                   COUNT(*) AS n,
                   ROUND(100.0*AVG((top_pick_correct)::int), 1) AS win_pct,
                   ROUND(100.0*AVG((in_the_money)::int), 1) AS itm_pct
            FROM race_predictions
            WHERE result_fetched AND top_pick_is_favorite IS NOT NULL
            GROUP BY 1 ORDER BY 1 DESC NULLS LAST
            """
        )
        if not rows:
            print("  (no settled picks with market data yet — capture began 2026-06-04)")
        else:
            for r in rows:
                lbl = "picked FAVORITE" if r["is_fav"] else "picked non-favorite"
                print(f"  {lbl:20} n={r['n']:<5} win={r['win_pct']}%  itm={r['itm_pct']}%")

        print("=== win rate by field size ===")
        rows = await c.fetch(
            """
            SELECT CASE WHEN field_size <= 6 THEN '1) <=6'
                        WHEN field_size <= 9 THEN '2) 7-9'
                        WHEN field_size <= 12 THEN '3) 10-12'
                        ELSE '4) 13+' END AS bucket,
                   COUNT(*) AS n,
                   ROUND(100.0*AVG((top_pick_correct)::int), 1) AS win_pct
            FROM race_predictions
            WHERE result_fetched AND field_size IS NOT NULL
            GROUP BY 1 ORDER BY 1
            """
        )
        if not rows:
            print("  (no data yet)")
        else:
            for r in rows:
                print(f"  field {r['bucket']:9} n={r['n']:<5} win={r['win_pct']}%")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
