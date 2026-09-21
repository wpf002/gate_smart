"""The nightly warms a slate, not the whole card.

What matters here is not that the count is right — it is that the right races
are on it: the tracks someone actually opens, the feature races, and enough
spread across the rest that the reflection loop still learns from a broad
sample rather than one meet.
"""
import importlib.util
import os
import sys

_SPEC = importlib.util.spec_from_file_location(
    "nightly_predict_all",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "nightly_predict_all.py"),
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
npa = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(npa)


def race(track: str, num: int, *, title: str = "", purse: str = "") -> tuple:
    return (
        {
            "race_id": f"{track}_1789689600000-{num}",
            "course": track,
            "title": title or f"Race {num}",
            "prize": purse,
            "off_dt": f"2026-09-20T{16 + num:02d}:00:00Z",
        },
        "na",
    )


def card(tracks: int = 10, per_track: int = 10) -> list:
    return [
        race(f"T{t}", n)
        for t in range(tracks)
        for n in range(per_track)
    ]


def tracks_of(entries) -> set:
    return {npa._track_of(r) for r, _ in entries}


def test_small_card_is_taken_whole():
    entries = card(tracks=2, per_track=5)
    chosen, why = npa.select_slate(entries, 40, set())
    assert chosen == entries
    assert why == {"whole card": 10}


def test_sampling_off_takes_everything():
    entries = card()
    chosen, _ = npa.select_slate(entries, 0, set())
    assert len(chosen) == 100


def test_slate_holds_to_its_size():
    chosen, _ = npa.select_slate(card(), 40, set())
    assert len(chosen) == 40


def test_every_race_at_a_used_track_is_warmed():
    entries = card()
    chosen, why = npa.select_slate(entries, 40, {"T3"})
    warmed = {npa._race_key(r) for r, _ in chosen}
    for r, _ in entries:
        if npa._track_of(r) == "T3":
            assert npa._race_key(r) in warmed
    assert why["used track"] == 10


def test_feature_races_make_the_slate_at_an_unused_track():
    entries = card(tracks=10, per_track=10)
    entries.append(race("T9", 99, title="Durham Cup S."))
    entries.append(race("T9", 98, purse="$150,000"))
    chosen, why = npa.select_slate(entries, 25, set())
    titles = {(r.get("title") or "") for r, _ in chosen}
    assert "Durham Cup S." in titles
    assert why["feature"] == 2


def test_the_rest_spreads_across_tracks_instead_of_draining_one():
    chosen, why = npa.select_slate(card(tracks=10, per_track=10), 40, set())
    assert len(tracks_of(chosen)) == 10, "a spread pass that lands on one meet teaches the loop nothing"
    assert why["spread"] == 40


def test_used_tracks_can_fill_the_slate_without_overflowing():
    chosen, why = npa.select_slate(card(tracks=10, per_track=10), 15, {"T1", "T2"})
    assert len(chosen) == 15
    assert why["used track"] == 15
    assert tracks_of(chosen) <= {"T1", "T2"}


def test_slate_keeps_the_card_order():
    entries = card()
    chosen, _ = npa.select_slate(entries, 40, {"T7"})
    order = {npa._race_key(r): n for n, (r, _) in enumerate(entries)}
    positions = [order[npa._race_key(r)] for r, _ in chosen]
    assert positions == sorted(positions)


def test_purse_parsing_handles_the_feed_shapes():
    assert npa._purse_usd({"prize": "$26,400"}) == 26400
    assert npa._purse_usd({"prize": 150000}) == 150000
    assert npa._purse_usd({"prize": "150000.00"}) == 150000
    assert npa._purse_usd({}) == 0


def test_track_comes_from_the_race_id_prefix():
    assert npa._track_of({"race_id": "ALB_1789689600000-1"}) == "ALB"
    assert npa._track_of({"course": "Saratoga"}) == "SARATOGA"


def test_a_maiden_claimer_is_not_a_feature_race():
    assert not npa._is_feature({"title": "Maiden Claiming", "prize": "$26,400"})
    assert npa._is_feature({"title": "Sweet Briar Too S."})
    assert npa._is_feature({"title": "Race 7", "prize": "$120,000"})
