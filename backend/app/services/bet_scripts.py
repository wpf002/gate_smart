"""
Teller scripts and box options, built from the picks rather than written by Claude.

These were part of the JSON schema, so Sonnet wrote four teller lines and two
exotic-box strings for every race on the card. Output tokens are ~70% of the cost
of a race analysis, and none of this text is a judgement — it is the selections
restated in betting-window phrasing. Generating it here keeps the feature and
stops paying per race for it.

The frontend already had a fallback for the win/place/show lines; it just lacked
the race number, so the model's version was preferred when present. These build
the complete line, which makes the model's version redundant rather than better.
"""

_STRAIGHT = ("win", "place", "show")
_SPOKEN = {
    "exacta": "Exacta",
    "trifecta": "Trifecta",
    "superfecta": "Superfecta",
    "daily_double": "Daily Double",
}


def _stake_dollars(rec: dict) -> str:
    """Dollar amount from the model's stake suggestion, defaulting to the $2 base."""
    import re

    text = str((rec or {}).get("stake_suggestion") or "")
    found = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
    if not found:
        return "2"
    amount = found.group(1)
    # Trim only a decimal tail: "12.50" -> "12.5", but "10" must stay "10".
    return amount.rstrip("0").rstrip(".") if "." in amount else amount


def _race_phrase(race_number) -> str:
    number = str(race_number or "").strip()
    return f", race {number}" if number else ""


def build_teller_scripts(bet_recommendations: dict, race_number=None) -> dict:
    """What to say at the window, one line per recommended bet.

    Exotics keep the "N over M" phrasing a teller expects rather than the
    slash-separated selection string the JSON carries.
    """
    scripts: dict[str, str] = {}
    for bet_type, rec in (bet_recommendations or {}).items():
        selection = str((rec or {}).get("selection") or "").strip()
        if not selection:
            continue
        stake = _stake_dollars(rec)
        race = _race_phrase(race_number)

        if bet_type in _STRAIGHT:
            scripts[bet_type] = f"Say to teller: '${stake} to {bet_type} on {selection}{race}'"
        elif bet_type in _SPOKEN:
            legs = [p.strip() for p in selection.replace(",", "/").split("/") if p.strip()]
            spoken = " over ".join(legs) if len(legs) > 1 else selection
            scripts[bet_type] = f"Say to teller: '${stake} {_SPOKEN[bet_type]}, {spoken}{race}'"
    return scripts


def build_box_option(rec: dict) -> str | None:
    """Cost of boxing an exacta — every ordering of the same horses.

    A 2-horse exacta box is 2 combinations, so it costs one extra unit. Returns
    None when the selection is not a multi-horse exotic.
    """
    selection = str((rec or {}).get("selection") or "").strip()
    legs = [p.strip() for p in selection.replace(",", "/").split("/") if p.strip()]
    if len(legs) < 2:
        return None
    import math

    combinations = math.perm(len(legs), len(legs))
    stake = float(_stake_dollars(rec) or 2)
    extra = stake * (combinations - 1)
    joined = "-".join(legs)
    return f"Box {joined} for ${extra:.0f} more ({combinations} combinations)"


def attach_bet_scripts(data: dict, race_number=None) -> dict:
    """Fill in the derived betting text on a finished analysis. Mutates in place."""
    recs = data.get("bet_recommendations") or {}
    if not recs:
        return data
    data["teller_script"] = build_teller_scripts(recs, race_number)
    exacta = recs.get("exacta")
    if isinstance(exacta, dict):
        box = build_box_option(exacta)
        if box:
            exacta["box_option"] = box
    return data
