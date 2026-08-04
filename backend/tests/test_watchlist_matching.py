"""
Tests for the watchlist matcher — the logic that surfaces which followed
horses/trainers/jockeys are entered in the upcoming cards.
"""
from types import SimpleNamespace

from app.api.routes.watchlist import build_watchlist_matches, normalize_entity


def _item(t, key, label):
    return SimpleNamespace(entity_type=t, entity_key=key, entity_label=label)


def _runner(**kw):
    base = {"horse_name": "", "horse_id": "", "trainer": "", "jockey": "", "number": "1"}
    base.update(kw)
    return base


def _race(rid="R1", runners=None, **kw):
    return {"race_id": rid, "course": "Saratoga", "race_name": "Race 1",
            "off_dt": "2026-07-22T18:00:00+00:00", "runners": runners or [], **kw}


def test_normalize_handles_case_apostrophe_hyphen():
    assert normalize_entity("O'Brien") == normalize_entity("obrien")
    assert normalize_entity("Jean-Luc  Smith") == "jean luc smith"
    assert normalize_entity(None) == ""


def test_matches_trainer_and_jockey_by_name():
    items = [_item("trainer", normalize_entity("Todd Pletcher"), "Todd Pletcher"),
             _item("jockey", normalize_entity("Irad Ortiz"), "Irad Ortiz")]
    cards = {"today": [_race(runners=[
        _runner(horse_name="Fast Horse", trainer="Todd Pletcher", jockey="Irad Ortiz"),
    ])]}
    m = build_watchlist_matches(items, cards)
    kinds = sorted(x["entity_type"] for x in m)
    assert kinds == ["jockey", "trainer"]
    assert all(x["race_id"] == "R1" for x in m)


def test_matches_horse_by_id_or_name():
    items = [_item("horse", normalize_entity("Flightline"), "Flightline")]
    cards = {"today": [_race(runners=[_runner(horse_name="Flightline")])]}
    assert len(build_watchlist_matches(items, cards)) == 1
    # also matches by horse_id
    items2 = [_item("horse", normalize_entity("REG123"), "Flightline")]
    cards2 = {"today": [_race(runners=[_runner(horse_name="Flightline", horse_id="REG123")])]}
    assert len(build_watchlist_matches(items2, cards2)) == 1


def test_skips_scratched_runners():
    items = [_item("jockey", normalize_entity("Irad Ortiz"), "Irad Ortiz")]
    cards = {"today": [_race(runners=[_runner(jockey="Irad Ortiz", scratched=True)])]}
    assert build_watchlist_matches(items, cards) == []


def test_dedups_same_entity_same_race():
    # A trainer AND jockey the user follows on the same runner -> two matches
    # (different entities); but the same trainer twice in one race -> one.
    items = [_item("trainer", normalize_entity("Bob Baffert"), "Bob Baffert")]
    cards = {"today": [_race(runners=[
        _runner(horse_name="A", trainer="Bob Baffert"),
        _runner(horse_name="B", trainer="Bob Baffert"),
    ])]}
    m = build_watchlist_matches(items, cards)
    assert len(m) == 1  # one match per (entity, race), not per runner


def test_unfollowed_entities_do_not_match():
    items = [_item("jockey", normalize_entity("Irad Ortiz"), "Irad Ortiz")]
    cards = {"today": [_race(runners=[_runner(jockey="John Velazquez")])]}
    assert build_watchlist_matches(items, cards) == []


def test_empty_watchlist_returns_empty():
    assert build_watchlist_matches([], {"today": [_race(runners=[_runner(jockey="x")])]}) == []
