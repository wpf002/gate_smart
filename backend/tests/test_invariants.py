"""
Checks that production is doing the right thing, not merely that it is up.

Every check here exists because a real regression reached production without
raising: the losing pick model ran for three days after an env var was reset
outside the repo, an analysis cache was warmed under a key nothing read, 517k
junk rows entered the form archive, and a jsonb null was counted as control
evidence for lessons it never carried. No health check went red for any of them.

The hard constraint is silence on healthy days. The owner runs this alone; an
alert that fires when nothing is wrong gets filtered, and then it is not an
alert. Racing data is legitimately irregular — light Monday cards, tracks going
dark, feeds dropping meets — so every threshold here is deliberately loose.
"""
import pytest

from app.services import invariants


class FakeDB:
    """Returns canned rows for each SQL the checks issue, in call order."""

    def __init__(self, *batches):
        self._batches = list(batches)

    async def execute(self, *_args, **_kw):
        rows = self._batches.pop(0) if self._batches else []

        class R:
            def all(self_inner):
                return rows

        return R()


@pytest.mark.asyncio
async def test_a_wrong_production_model_is_caught():
    """The Haiku regression: config said one thing, behaviour did another."""
    from app.services.secretariat import PICK_MODEL_CHALLENGER

    db = FakeDB([(PICK_MODEL_CHALLENGER, 150)])  # 100% challenger while percent is 0
    msg = await invariants.check_pick_model_mix(db)
    assert msg and "disagree" in msg


@pytest.mark.asyncio
async def test_an_unknown_model_is_caught():
    db = FakeDB([("claude-something-else", 120)])
    msg = await invariants.check_pick_model_mix(db)
    assert msg and "unrecognised" in msg


@pytest.mark.asyncio
async def test_a_light_card_is_never_flagged():
    """A Monday slate of 12 races is real racing, not a failure. Flagging it
    would train the owner to ignore the alert."""
    from app.services.secretariat import PICK_MODEL_CHALLENGER

    assert await invariants.check_pick_model_mix(FakeDB([(PICK_MODEL_CHALLENGER, 12)])) is None
    assert await invariants.check_slate_coverage(FakeDB([(15, 3)])) is None


@pytest.mark.asyncio
async def test_the_expected_model_split_is_silent():
    from app.services.secretariat import PICK_MODEL_DEFAULT

    assert await invariants.check_pick_model_mix(FakeDB([(PICK_MODEL_DEFAULT, 150)])) is None


@pytest.mark.asyncio
async def test_the_jsonb_null_leak_is_caught():
    assert await invariants.check_provenance_shape(FakeDB([(78,)])) is not None
    assert await invariants.check_provenance_shape(FakeDB([(0,)])) is None


@pytest.mark.asyncio
async def test_form_archive_corruption_is_caught():
    """The also_ran character-split signature, now watched on the live path and
    not only in the backfill script."""
    assert await invariants.check_form_archive_integrity(FakeDB([(517, 0)])) is not None
    assert await invariants.check_form_archive_integrity(FakeDB([(0, 41)])) is not None
    assert await invariants.check_form_archive_integrity(FakeDB([(0, 0)])) is None


@pytest.mark.asyncio
async def test_contradictory_grading_is_caught():
    """A winning pick that is not in the money means the scoring every reported
    percentage rests on is broken."""
    assert await invariants.check_grading_self_consistency(FakeDB([(4,)])) is not None
    assert await invariants.check_grading_self_consistency(FakeDB([(0,)])) is None


@pytest.mark.asyncio
async def test_half_settled_slate_is_caught():
    msg = await invariants.check_slate_coverage(FakeDB([(150, 60)]))
    assert msg and "subset" in msg
    assert await invariants.check_slate_coverage(FakeDB([(150, 148)])) is None


@pytest.mark.asyncio
async def test_cost_blowout_is_caught_and_a_quiet_day_is_not():
    assert await invariants.check_cost_per_pick(FakeDB([(30.0, 100)])) is not None   # $0.30/pick
    assert await invariants.check_cost_per_pick(FakeDB([(3.7, 100)])) is None        # $0.037/pick
    assert await invariants.check_cost_per_pick(FakeDB([(0, 0)])) is None            # no calls


@pytest.mark.asyncio
async def test_a_check_that_raises_is_reported_not_swallowed():
    """A check that silently stops checking is the exact failure mode this
    module exists to prevent."""
    class Boom:
        async def execute(self, *_a, **_k):
            raise RuntimeError("column vanished")

    msg = None
    try:
        await invariants.check_provenance_shape(Boom())
    except RuntimeError:
        msg = "raised"
    assert msg == "raised", "checks must propagate so run_invariants can report them"


def test_every_check_is_registered():
    """A check nobody runs is worse than no check — it reads as coverage."""
    registered = {fn for _label, fn in invariants.CHECKS}
    defined = {
        getattr(invariants, n) for n in dir(invariants)
        if n.startswith("check_") and callable(getattr(invariants, n))
    }
    assert defined == registered, "every check_* must appear in CHECKS"
