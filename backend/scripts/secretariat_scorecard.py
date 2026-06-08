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
import math
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


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson confidence interval for a win rate, as percentages.

    This is the noise band: with only ~130 races/day a true 19% rate routinely
    *measures* anywhere from ~12% to ~26% on luck alone. The CI makes that
    explicit so a daily/weekly bounce isn't mistaken for learning.
    """
    if not n:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (100 * (centre - half), 100 * (centre + half))


async def main() -> None:
    c = await asyncpg.connect(_dsn())
    try:
        print("=== Secretariat scorecard — weekly cohorts (races-weighted) ===")
        rows = await c.fetch(
            """
            SELECT date_trunc('week', report_date)::date AS wk,
                   SUM(total_races) AS races,
                   SUM(top_pick_wins) AS wins,
                   ROUND(100.0*SUM(top_pick_wins)/NULLIF(SUM(total_races),0), 1) AS win_pct,
                   ROUND(100.0*SUM(in_the_money)/NULLIF(SUM(total_races),0), 1) AS itm_pct
            FROM daily_accuracy_reports
            WHERE total_races > 0
            GROUP BY 1 ORDER BY 1
            """
        )
        print(f"  {'week_of':12} {'races':>6} {'win%':>6} {'95% CI':>14} {'itm%':>6}")
        for r in rows:
            lo, hi = _wilson(r["wins"] or 0, r["races"] or 0)
            ci = f"[{lo:.0f}-{hi:.0f}%]"
            flag = "  <- loop alive" if str(r["wk"]) >= LOOP_FIX_DATE else ""
            print(f"  {str(r['wk']):12} {r['races']:>6} {r['win_pct']:>6} {ci:>14} {r['itm_pct']:>6}{flag}")

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
        sample = cal["sample_size"] or 0
        rlo, rhi = _wilson(round((cal["rolling_win_rate"] or 0) * sample), sample)
        print("\n=== current rolling ===")
        print(f"  rolling_win_rate={rolling}%  95% CI [{rlo:.1f}-{rhi:.1f}%]  sample={sample}  updated={cal['updated_at']:%Y-%m-%d %H:%M}")
        print(f"  favorite baseline ~{FAVORITE_BASELINE_PCT}%  |  target {TARGET_PCT}-35%  |  gap to target: {TARGET_PCT-rolling:+.1f} pts")
        # Noise floor — how much a single day/week swings on luck alone at this rate.
        for label, n in [("a 130-race day", 130), ("a 600-race week", 600)]:
            lo, hi = _wilson(round(rolling / 100 * n), n)
            print(f"  noise on {label}: ±{(hi - lo) / 2:.1f} pts (95%) — moves inside this band are NOT learning")
        print("  => judge learning by the rolling CI trending up over WEEKS, or by favorite-agreement below (near noise-free).")

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
                   SUM((top_pick_correct)::int) AS wins,
                   ROUND(100.0*AVG((top_pick_correct)::int), 1) AS win_pct,
                   ROUND(100.0*AVG((in_the_money)::int), 1) AS itm_pct
            FROM race_predictions
            WHERE race_date >= '2026-06-04' AND result_fetched AND top_pick_is_favorite IS NOT NULL
            GROUP BY 1 ORDER BY 1 DESC NULLS LAST
            """
        )
        if not rows:
            print("  (no settled picks with market data yet — capture began 2026-06-04)")
        else:
            for r in rows:
                lbl = "picked FAVORITE" if r["is_fav"] else "picked non-favorite"
                lo, hi = _wilson(r["wins"] or 0, r["n"] or 0)
                print(f"  {lbl:20} n={r['n']:<5} win={r['win_pct']}% [{lo:.0f}-{hi:.0f}%]  itm={r['itm_pct']}%")

        # LEADING INDICATOR — favorite-agreement % per day. This is a property of
        # the PICKS, not race outcomes, so it barely fluctuates. If the
        # market-anchoring change works, this line jumps within a day — no waiting
        # weeks for the noisy win rate to confirm. Watch this number.
        print("\n=== favorite-agreement % per day (leading indicator — near noise-free) ===")
        rows = await c.fetch(
            """
            SELECT race_date,
                   COUNT(top_pick_is_favorite) AS picks,
                   ROUND(100.0*AVG((top_pick_is_favorite)::int), 1) AS fav_share
            FROM race_predictions
            WHERE race_date >= '2026-06-04' AND top_pick_is_favorite IS NOT NULL
            GROUP BY 1 ORDER BY 1
            """
        )
        for r in rows:
            print(f"  {str(r['race_date']):12} picks={r['picks']:<4} picked-favorite={r['fav_share']}%")

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
            WHERE race_date >= '2026-06-04' AND result_fetched AND field_size IS NOT NULL
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
