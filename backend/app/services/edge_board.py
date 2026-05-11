"""
Edge Board — ranks today's races by Secretariat's edge over the public.

Reads the locked nightly analyses cached by nightly_predict_all.py and
compares each top pick's fair odds (Secretariat's price) to the morning
line (the public's price). Surfaces only overlays — spots where market
odds materially exceed fair odds — sorted by gap.

This is the CAW posture applied to a retail tool: rather than treating
every pick as equally interesting, surface the races where Secretariat
thinks the public is most wrong.
"""
from typing import Optional

from app.core.cache import cache_get
from app.services.secretariat import compute_input_fingerprint

# Must match nightly_predict_all.LOCK_MODE — that's the cache key the
# nightly Sonnet pass writes to.
_LOCK_MODE = "medium"


def _parse_decimal(odds) -> Optional[float]:
    """Convert '3/1', '7/2', or '2.50' into decimal odds (4.0, 4.5, 2.5)."""
    if not odds:
        return None
    s = str(odds).strip()
    if not s or s.upper() in ("SP", "?", "EVS", "EVENS"):
        return None
    if "/" in s:
        try:
            n, d = s.split("/")
            return int(n) / int(d) + 1
        except (ValueError, ZeroDivisionError):
            return None
    try:
        v = float(s)
        return v if v > 1 else None
    except (ValueError, TypeError):
        return None


def _norm(name: str) -> str:
    return (name or "").lower().strip().replace("'", "").replace("-", " ")


def _find_runner(runners: list, horse_name: str, program_num: Optional[str]) -> Optional[dict]:
    """Match a horse across the analysis output and the live racecard.

    Program number is the most reliable key (the LLM echoes it from input,
    and racecards always carry it); fall back to a normalized name match
    when the number is missing.
    """
    if program_num:
        target_num = str(program_num).lstrip("#").strip()
        for r in runners:
            num = str(
                r.get("number")
                or r.get("program_number")
                or r.get("cloth_number")
                or ""
            ).lstrip("#").strip()
            if num and num == target_num:
                return r
    target_name = _norm(horse_name)
    if not target_name:
        return None
    for r in runners:
        name = r.get("horse") or r.get("horse_name") or r.get("name") or ""
        if _norm(name) == target_name:
            return r
    return None


def _post_time_et(race: dict) -> Optional[str]:
    """Best-effort HH:MM ET post time from a race record."""
    off_dt = race.get("off_dt") or race.get("off_time")
    if off_dt:
        import re
        m = re.search(r"T(\d{2}:\d{2})", str(off_dt))
        if m:
            h, mn = map(int, m.group(1).split(":"))
            # Match nightly_predict_all's UTC→ET conversion (EDT, -4)
            h_et = (h - 4) % 24
            return f"{h_et:02d}:{mn:02d}"
    raw = race.get("time") or race.get("post_time") or ""
    return str(raw)[:5] if raw else None


async def compute_edge_board(
    racecards: list[dict],
    min_value_percent: float = 10.0,
    max_picks: int = 7,
) -> list[dict]:
    """Build today's Edge Board from already-fetched racecards.

    For each race:
      1. Look up the locked nightly analysis (cache key matches
         nightly_predict_all's write key).
      2. Read the top pick's fair_odds from the analysis.
      3. Read the same horse's market odds (morning line) from the racecard.
      4. value_percent = (market_decimal - fair_decimal) / fair_decimal * 100.
         Positive = overlay (market priced longer than fair).

    Returns the top `max_picks` overlays meeting `min_value_percent`,
    sorted by value_percent descending. Caller passes pre-fetched data
    so we don't re-hit the racing API.
    """
    rows: list[dict] = []
    for race in racecards:
        race_id = race.get("race_id") or race.get("id") or ""
        if not race_id:
            continue

        fp = compute_input_fingerprint(race)
        analysis = await cache_get(f"ai_analysis:{race_id}:{_LOCK_MODE}:{fp}")
        if not analysis:
            continue

        pf_first = (analysis.get("predicted_finish") or {}).get("first")
        if isinstance(pf_first, dict):
            top_name = pf_first.get("horse_name") or pf_first.get("name") or ""
            top_num = str(pf_first.get("number") or "").lstrip("#").strip() or None
        else:
            top_name = pf_first or ""
            top_num = None
        if not top_name:
            continue

        analysis_runner = _find_runner(analysis.get("runners") or [], top_name, top_num)
        if not analysis_runner:
            continue
        fair_odds_str = analysis_runner.get("fair_odds") or ""
        fair_dec = _parse_decimal(fair_odds_str)
        if not fair_dec:
            continue

        market_runner = _find_runner(race.get("runners") or [], top_name, top_num)
        if not market_runner:
            continue
        market_odds_str = (
            market_runner.get("odds")
            or market_runner.get("ml_odds")
            or market_runner.get("morning_line")
            or market_runner.get("sp")
            or ""
        )
        market_dec = _parse_decimal(market_odds_str)
        if not market_dec:
            continue

        value_percent = (market_dec - fair_dec) / fair_dec * 100
        if value_percent < min_value_percent:
            continue

        rows.append({
            "race_id": race_id,
            "track_code": (
                race.get("course_id") or race.get("course") or race.get("track_code") or ""
            )[:10],
            "race_name": race.get("race_name") or race.get("title") or "",
            "race_type": race.get("race_type") or race.get("type") or "",
            "post_time_et": _post_time_et(race),
            "horse_name": top_name,
            "program_num": top_num
                or str(analysis_runner.get("number") or "").lstrip("#").strip()
                or None,
            "fair_odds": fair_odds_str,
            "fair_decimal": round(fair_dec, 2),
            "market_odds": str(market_odds_str),
            "market_decimal": round(market_dec, 2),
            "value_percent": round(value_percent, 1),
            "value_score": analysis_runner.get("value_score"),
            "confidence": analysis.get("confidence"),
        })

    rows.sort(key=lambda r: r["value_percent"], reverse=True)
    return rows[:max_picks]
