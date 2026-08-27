"""
Why Secretariat left the favorite out of the win slot — as a scoreable category.

Fading is the single biggest lever on the win rate: siding with the morning-line
favorite wins ~34%, fading wins ~17%, and fades happen in most races. The prompt
already demands a specific reason before diverging, but that reason only ever
existed as free prose, so "which reasons actually win?" was unanswerable.

This pins the reason to a fixed vocabulary. The goal is not to fade less — it is
to find out which fades are the good ones, so the ~17% can climb without giving
up the price entirely.
"""
import re

# Deliberately the same angles the prompt names as legitimate grounds to
# diverge. Anything outside this list is not a reason, it is a preference.
FADE_REASONS: dict[str, str] = {
    "lone_speed": "an uncontested front-runner the favorite cannot run down",
    "pace_collapse": "the favorite is in a speed duel it will not survive",
    "class_drop": "my pick is dropping in class against this field",
    "class_jump": "the favorite is stepping up in class",
    "bounce": "the favorite is regressing off a peak effort",
    "run_style": "the favorite's run style does not fit the projected pace",
    "trip_bias": "a troubled trip or track bias distorted the favorite's form",
    "form_cycle": "my pick's form cycle is peaking and the favorite's is not",
    "connections": "a jockey or trainer change that materially matters",
}

# Recorded when the top pick IS the favorite, so agreement is distinguishable
# from a fade with a missing reason.
NO_FADE = "sided_with_favorite"
# Recorded when the model faded but named nothing in the vocabulary. Kept as its
# own bucket rather than dropped: an unexplained fade is exactly the habit worth
# measuring, and hiding it would flatter the numbers.
UNSPECIFIED = "unspecified"

_ALIASES: list[tuple[str, str]] = [
    (r"lone[\s_-]*speed|uncontested lead|clear early speed", "lone_speed"),
    (r"pace[\s_-]*(collapse|duel|meltdown|pressure)|speed duel", "pace_collapse"),
    (r"class[\s_-]*(drop|relief)|dropping (in )?class", "class_drop"),
    (r"class[\s_-]*(jump|rise|hike)|stepping up", "class_jump"),
    (r"bounce|regress(ing|ion)?|off a peak", "bounce"),
    (r"run[\s_-]*style|running style|pace fit|does ?n[o']?t fit the pace", "run_style"),
    (r"trip|bias|troubled", "trip_bias"),
    (r"form[\s_-]*cycle|improving form|peaking", "form_cycle"),
    (r"jockey|trainer|connections|rider (change|switch)", "connections"),
]


def normalize_fade_reason(raw: str, top_pick_is_favorite: bool | None = None) -> str:
    """Map whatever the model returned onto the fixed vocabulary.

    `top_pick_is_favorite` wins over the text: if Secretariat sided with the
    market, no fade happened regardless of what it wrote in the field.
    """
    if top_pick_is_favorite:
        return NO_FADE
    text = str(raw or "").strip().lower()
    if not text:
        return UNSPECIFIED
    key = re.sub(r"[^a-z_]+", "_", text).strip("_")
    if key in FADE_REASONS:
        return key
    for pattern, canonical in _ALIASES:
        if re.search(pattern, text):
            return canonical
    return UNSPECIFIED


def prompt_block() -> str:
    """The instruction that makes the field answerable rather than decorative."""
    options = "\n".join(f"    {k} — {v}" for k, v in FADE_REASONS.items())
    return (
        "\nFADE REASON. If predicted_finish.first is NOT the morning-line favorite, "
        "you are fading the market, and the JSON field \"fade_reason\" must name which "
        "of these applies:\n" + options + "\n"
        "    If none of them genuinely applies, you do not have a reason to fade — "
        "put the favorite first instead.\n"
        "If predicted_finish.first IS the favorite, set fade_reason to "
        f"\"{NO_FADE}\".\n"
    )
