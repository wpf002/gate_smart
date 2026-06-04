"""
Odds parsing + market context for Secretariat picks.

Captures the single most predictive variable in racing — the betting market —
so we can measure favorite-agreement and calibration of the model's picks.

Morning-line odds arrive as fractional strings ("5/2", "9/5", "even", "7-2").
We convert to a fractional-decimal scalar where **lower = more favored**, so the
race favorite is simply the active runner with the minimum value.
"""
from __future__ import annotations

import re
from typing import Optional


def parse_odds_to_decimal(raw) -> Optional[float]:
    """Convert a morning-line odds string to a fractional-decimal scalar.

    '5/2' -> 2.5, '9/5' -> 1.8, 'even'/'evs'/'1/1' -> 1.0, '7-2' -> 3.5,
    '3' -> 3.0. Lower = more favored. Returns None if unparseable/non-positive
    (e.g. scratched runners, 'SCR', '', None).
    """
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s or s in ("scr", "scratched", "ml", "-", "n/a"):
        return None
    if s in ("even", "evens", "evs"):
        return 1.0
    # Normalize "7-2" style to "7/2"
    s = s.replace("-", "/")
    try:
        if "/" in s:
            num, den = s.split("/", 1)
            num_f, den_f = float(num), float(den)
            if den_f == 0:
                return None
            val = num_f / den_f
        else:
            val = float(s)
    except (ValueError, ZeroDivisionError):
        return None
    return val if val > 0 else None


def _norm_name(name) -> str:
    """Lowercased, alphanumeric-only — for matching pick name to a runner."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def _runner_odds(runner: dict) -> Optional[float]:
    return parse_odds_to_decimal(runner.get("odds") or runner.get("sp"))


def _runner_num(runner: dict) -> str:
    return str(
        runner.get("program_number")
        or runner.get("number")
        or runner.get("cloth_number")
        or ""
    ).lstrip("#").strip()


def compute_market_context(
    runners: list[dict],
    pick_name: Optional[str] = None,
    pick_num: Optional[str] = None,
) -> dict:
    """Derive market context for a race + Secretariat's top pick.

    Returns keys: field_size, favorite_num, favorite_odds, top_pick_odds,
    top_pick_is_favorite. Any value may be None when the data is missing
    (e.g. no morning-line odds published, pick not matched to a runner).
    """
    out = {
        "field_size": None,
        "favorite_num": None,
        "favorite_odds": None,
        "top_pick_odds": None,
        "top_pick_is_favorite": None,
    }
    if not runners:
        return out

    active = [
        r for r in runners
        if not r.get("scratched") and not r.get("non_runner")
    ]
    out["field_size"] = len(active)

    # Favorite = active runner with the lowest parsed odds.
    fav = None
    fav_odds = None
    for r in active:
        o = _runner_odds(r)
        if o is None:
            continue
        if fav_odds is None or o < fav_odds:
            fav_odds = o
            fav = r
    if fav is not None:
        out["favorite_num"] = _runner_num(fav) or None
        out["favorite_odds"] = fav_odds

    # Match the pick to a runner: program number first, then normalized name.
    pick_num_s = str(pick_num or "").lstrip("#").strip()
    pick_runner = None
    if pick_num_s:
        pick_runner = next((r for r in active if _runner_num(r) == pick_num_s), None)
    if pick_runner is None and pick_name:
        target = _norm_name(pick_name)
        if target:
            pick_runner = next(
                (r for r in active if _norm_name(r.get("horse_name") or r.get("horse") or r.get("name")) == target),
                None,
            )
    if pick_runner is not None:
        out["top_pick_odds"] = _runner_odds(pick_runner)

    # Did Secretariat pick the market favorite? Prefer program-number identity.
    if out["favorite_num"] and pick_runner is not None and _runner_num(pick_runner):
        out["top_pick_is_favorite"] = _runner_num(pick_runner) == out["favorite_num"]
    elif out["top_pick_odds"] is not None and out["favorite_odds"] is not None:
        out["top_pick_is_favorite"] = abs(out["top_pick_odds"] - out["favorite_odds"]) < 1e-9

    return out
