"""
Turn a lesson's prose into a testable scope.

A lesson like "When a claiming or maiden claiming race has a heavy chalk..."
only means anything over the races it actually governs. Extracting that scope is
what turns the sentence into a population we can score. Without it a lesson is
unfalsifiable — which is how fourteen of them accumulated in memory while the
win rate stayed flat for nineteen weeks.

Deliberately deterministic, with no model call. A scope decides which races count
as evidence for or against a lesson, so it has to be reproducible and auditable
rather than re-inferred (and quietly re-worded) every night.
"""
import re

# Longest phrase first: "maiden claiming" must win over "claiming", and
# "allowance optional claiming" over both "allowance" and "optional claiming".
# Values on the right are the exact strings race_predictions.race_type stores.
RACE_TYPE_PHRASES: list[tuple[str, str]] = [
    ("allowance optional claiming", "ALLOWANCE OPTIONAL CLAIMING"),
    ("starter optional claiming", "STARTER OPTIONAL CLAIMING"),
    ("maiden optional claiming", "MAIDEN OPTIONAL CLAIMING"),
    ("maiden special weight", "MAIDEN SPECIAL WEIGHT"),
    ("starter allowance", "STARTER ALLOWANCE"),
    ("maiden claiming", "MAIDEN CLAIMING"),
    ("optional claiming", "OPTIONAL CLAIMING"),
    ("handicap", "HANDICAP"),
    ("futurity", "FUTURITY"),
    ("claiming", "CLAIMING"),
    ("allowance", "ALLOWANCE"),
    ("maiden", "MAIDEN"),
    ("stakes", "STAKES"),
    ("trials", "TRIALS"),
]

SURFACE_PHRASES: list[tuple[str, str]] = [
    ("all-weather", "SYNTHETIC"),
    ("all weather", "SYNTHETIC"),
    ("synthetic", "SYNTHETIC"),
    ("tapeta", "SYNTHETIC"),
    ("polytrack", "SYNTHETIC"),
    ("turf", "TURF"),
    ("dirt", "DIRT"),
]

# "$2.40–$3.60", "$5-$15", "$2.10 to $3.40" — en dash, em dash or hyphen.
_PRICE_BAND = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:[-–—]|to)\s*\$?\s*(\d+(?:\.\d+)?)"
)


def _extract(text: str, phrases: list[tuple[str, str]]) -> list[str]:
    """Canonical values named in `text`, longest phrase first.

    Matched spans are blanked out as we go, so "maiden claiming" is not also
    counted as a bare "claiming" — while a genuinely separate "claiming"
    elsewhere in the sentence still registers.
    """
    working = (text or "").lower()
    found: list[str] = []
    for phrase, canonical in phrases:
        pattern = re.compile(r"\b" + re.escape(phrase) + r"\b")
        if pattern.search(working):
            if canonical not in found:
                found.append(canonical)
            working = pattern.sub(" " * len(phrase), working)
    return found


def canonical_race_type(raw: str) -> str | None:
    """The race_type a feed string denotes, or None if it names none.

    Most rows already hold a canonical value, but race_type also accepts
    composite strings, so this resolves those to the same vocabulary instead of
    letting them silently fall out of every scope.
    """
    if not raw:
        return None
    exact = str(raw).strip().upper()
    if exact in {c for _, c in RACE_TYPE_PHRASES}:
        return exact
    found = _extract(exact, RACE_TYPE_PHRASES)
    return found[0] if found else None


# Lessons are written as "When <condition>, I <action>, because <rationale>".
# Only the condition says which races the lesson governs. The rationale routinely
# names other categories in contrast — "turf form is more stable than dirt" — and
# reading scope from it made a turf lesson claim dirt races too.
_CONDITION_END = re.compile(r",\s+I\s|\bbecause\b|\bsince\b", re.IGNORECASE)
_LESSON_PREFIX = re.compile(r"^\s*(CHANGE|CONTINUE|WATCH)\s*:\s*", re.IGNORECASE)


def condition_clause(text: str) -> str:
    """The "when ..." part of a lesson — the only part that defines its scope."""
    body = _LESSON_PREFIX.sub("", text or "")
    cut = _CONDITION_END.search(body)
    return body[: cut.start()] if cut else body


def parse_scope(text: str) -> dict:
    """The races a lesson claims to govern.

    Empty `race_types`/`surfaces` mean "every race" — a general principle, scored
    against the whole card.

    Only the lesson's condition clause is read; see condition_clause.

    `price_band` is recorded for display but deliberately NOT used for matching.
    A band like "$2.40-$3.60" usually describes our own pick's odds, and
    selecting the evidence by an attribute of the pick would condition the
    measurement on the thing being measured. Scope matching stays on race_type
    and surface, which are fixed before Secretariat says anything.
    """
    condition = condition_clause(text)
    band = _PRICE_BAND.search(condition)
    return {
        "race_types": _extract(condition, RACE_TYPE_PHRASES),
        "surfaces": _extract(condition, SURFACE_PHRASES),
        "price_band": [float(band.group(1)), float(band.group(2))] if band else None,
    }


def race_matches_scope(race_type: str, surface: str, scope: dict) -> bool:
    """Whether one race counts as evidence for a lesson with this scope."""
    if not scope:
        return True

    wanted_types = scope.get("race_types") or []
    if wanted_types:
        if canonical_race_type(race_type) not in set(wanted_types):
            return False

    wanted_surfaces = scope.get("surfaces") or []
    if wanted_surfaces:
        found = _extract(str(surface or ""), SURFACE_PHRASES)
        if not found or found[0] not in set(wanted_surfaces):
            return False

    return True


def describe_scope(scope: dict) -> str:
    """Short human label for reports, e.g. "CLAIMING, MAIDEN CLAIMING (turf)"."""
    if not scope:
        return "all races"
    types = scope.get("race_types") or []
    surfaces = scope.get("surfaces") or []
    label = ", ".join(types) if types else "all races"
    if surfaces:
        label += " (" + ", ".join(s.lower() for s in surfaces) + ")"
    return label
