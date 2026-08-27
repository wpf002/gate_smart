"""
Fades, as a scoreable category.

Siding with the morning-line favorite wins ~34% over 10,001 races; fading wins
~16.7%, and Secretariat fades most of the time. The prompt has always demanded a
specific reason before diverging, but the reason lived only in free prose, so
every fade counted the same and "which fades are the good ones?" had no answer.

These tests hold the two properties that make the measurement trustworthy: an
agreement is never miscounted as a fade, and a fade with no real reason lands in
its own bucket rather than being quietly dropped.
"""
from app.services.fade_reason import (
    FADE_REASONS, NO_FADE, UNSPECIFIED, normalize_fade_reason, prompt_block,
)


def test_siding_with_the_favorite_is_never_a_fade():
    """The market fact outranks whatever the model wrote in the field — a pick
    that IS the favorite did not fade, whatever reason it volunteered."""
    assert normalize_fade_reason("lone_speed", top_pick_is_favorite=True) == NO_FADE
    assert normalize_fade_reason("", top_pick_is_favorite=True) == NO_FADE


def test_exact_vocabulary_passes_through():
    for key in FADE_REASONS:
        assert normalize_fade_reason(key, False) == key


def test_prose_maps_onto_the_vocabulary():
    cases = {
        "Lone speed — nobody presses him": "lone_speed",
        "the favorite is stepping up in class": "class_jump",
        "my pick is dropping in class": "class_drop",
        "he'll regress off a peak effort": "bounce",
        "troubled trip last out": "trip_bias",
        "speed duel up front": "pace_collapse",
        "jockey change to a live rider": "connections",
    }
    for text, expected in cases.items():
        assert normalize_fade_reason(text, False) == expected, text


def test_a_fade_without_a_real_reason_is_kept_as_unspecified():
    """Not dropped. An unexplained fade is exactly the habit worth measuring,
    and hiding it would flatter the numbers."""
    for junk in ("better value", "vibes", "", None, "he looks good"):
        assert normalize_fade_reason(junk, False) == UNSPECIFIED


def test_value_language_is_not_a_reason():
    """'Overbet' and 'better value' are explicitly NOT grounds to fade in the
    prompt — price belongs in bet recommendations, not in who wins."""
    assert normalize_fade_reason("the favorite is overbet", False) == UNSPECIFIED
    assert normalize_fade_reason("better value at the price", False) == UNSPECIFIED


def test_prompt_block_lists_every_reason_and_the_agreement_value():
    block = prompt_block()
    for key in FADE_REASONS:
        assert key in block
    assert NO_FADE in block
    # It must tell the model that no applicable reason means: take the favorite.
    assert "put the favorite first" in block
