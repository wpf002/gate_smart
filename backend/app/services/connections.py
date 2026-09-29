"""
Trainer and jockey form for the runners in one race.

Until the Pro plan these numbers did not exist for us at all: the NA feed ships
names and nothing else, and our own archive records a trainer or jockey only
when their horse ran top three, so it has wins but no start count. The prompt
said in as many words that it had "no win percentages for trainers, jockeys or
sires", and Secretariat handicapped connections on general knowledge alone.

The Pro analysis endpoints carry USA races and give a real denominator, plus
two figures worth more than a raw percentage:

  a/e   actual wins over the wins the market implied. Above 1.00 means the
        barn beats its own prices; a 25% trainer at 0.80 is being overbet.
  1_pl  profit on a flat unit backing every runner. Negative is normal.

Two limits, both load-bearing:

  The window is the plan's rolling twelve months, so this is recent form, not
  a career record.

  The core dataset holds 16,854 USA results for ALL years against the North
  America add-on's 107,447 for 2023-2026 alone — it is group races and selected
  handicaps, not the whole card. So these figures describe how a barn or rider
  does in stakes company. That is real information, and it is exactly why Jamie
  Ness, a claiming-circuit trainer, shows 97 starts here against 1,362 in our
  own 2023 charts. The block says which races it covers so nobody reads it as
  an overall strike rate.
"""
import asyncio

from app.services import racing_api

# Enough to cover a full field's connections without pushing the 5 req/sec cap;
# each person costs a search plus an analysis call on a cache miss.
_CONCURRENCY = 4

# Below this a percentage is noise. Claiming-circuit barns come back with a
# handful of runners in the core dataset, and "1 from 3, 33%" would read as a
# hot trainer when it means they had three stakes horses.
MIN_STARTS = 30


def _people(runners: list) -> list[tuple[str, str]]:
    """(name, type) for everyone with a live runner, de-duplicated."""
    seen: set[tuple[str, str]] = set()
    for r in runners or []:
        if r.get("scratched") or r.get("non_runner"):
            continue
        for field, kind in (("trainer", "trainer"), ("jockey", "jockey")):
            name = (r.get(field) or "").strip()
            if name and name.upper() != "SCRATCHED":
                seen.add((name, kind))
    return sorted(seen)


async def get_connections_form(runners: list) -> dict[tuple[str, str], dict]:
    """Recent-form records keyed by (name, type). Missing people are omitted."""
    people = _people(runners)
    if not people:
        return {}
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(name: str, kind: str):
        async with gate:
            try:
                return (name, kind), await racing_api.get_person_form(name, kind)
            except Exception:
                return (name, kind), None

    pairs = await asyncio.gather(*(one(n, k) for n, k in people))
    return {key: form for key, form in pairs
            if form and form.get("starts", 0) >= MIN_STARTS}


def render_connections_block(runners: list, form: dict[tuple[str, str], dict]) -> str:
    """One line per runner whose trainer or jockey we have numbers for."""
    if not form:
        return ""
    lines = []
    for r in runners or []:
        if r.get("scratched") or r.get("non_runner"):
            continue
        parts = []
        for field, kind, label in (("trainer", "trainer", "Trn"), ("jockey", "jockey", "Jky")):
            name = (r.get(field) or "").strip()
            rec = form.get((name, kind))
            if not rec:
                continue
            parts.append(
                f"{label} {name}: {rec['win_rate']:.0%} win, {rec['itm_rate']:.0%} ITM "
                f"({rec['starts']} starts), a/e {rec['ae']:.2f}, "
                f"{rec['profit_per_unit']:+.2f}/unit"
            )
        if parts:
            num = r.get("number") or "?"
            lines.append(f"#{num} {r.get('horse_name', '')}: " + " | ".join(parts))
    if not lines:
        return ""
    return (
        "\n\nCONNECTIONS IN STAKES COMPANY (rolling 12 months):\n"
        + "\n".join(lines)
        + "\n- THIS IS NOT AN OVERALL STRIKE RATE. It covers group races and selected "
          "handicaps only, so it says how these connections do in stakes company. A "
          "claiming barn may appear with few starts or not at all, which says nothing "
          "against them.\n"
        "- a/e is actual wins over the wins their prices implied. Above 1.00 means they "
        "beat the market; a high win rate at a low a/e is a barn the public already "
        "overbets.\n"
        "- /unit is profit on a flat stake backing every runner. Negative is normal — "
        "compare riders and barns against each other, not against zero.\n"
        f"- Anyone with fewer than {MIN_STARTS} starts on file is left out rather than "
        "shown as a percentage off a handful of runs."
    )


async def get_connections_context(runners: list) -> str:
    """The block, ready to drop into a prompt. Never raises."""
    try:
        return render_connections_block(runners, await get_connections_form(runners))
    except Exception as e:  # noqa: BLE001
        print(f"[connections] unavailable: {type(e).__name__}: {e}")
        return ""
