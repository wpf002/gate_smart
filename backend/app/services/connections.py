"""
Trainer, jockey and owner form for the runners in one race.

Until the Pro plan these numbers did not exist for us at all: the NA feed ships
names and nothing else, and our own archive records a trainer or jockey only
when their horse ran top three, so it has wins but no start count. The prompt
said in as many words that it had "no win percentages for trainers, jockeys or
sires", and Secretariat handicapped connections on general knowledge alone.

The Pro analysis endpoints carry USA races — a Godolphin lookup comes back with
Belmont, Saratoga, Keeneland, Churchill, Del Mar, Santa Anita, Aqueduct and
Gulfstream among its 166 courses — and give a real denominator, plus two
figures worth more than a raw percentage:

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
import re

from app.services import racing_api
from app.services.pedigree import bucket_for, furlongs_of

# Enough to cover a full field's connections without pushing the 5 req/sec cap;
# each person costs a search plus an analysis call on a cache miss.
_CONCURRENCY = 4

# Below this a percentage is noise. Claiming-circuit barns come back with a
# handful of runners in the core dataset, and "1 from 3, 33%" would read as a
# hot trainer when it means they had three stakes horses.
MIN_STARTS = 30

# A track record needs fewer starts to mean something than an overall one, but
# not so few that one winner reads as a pattern.
MIN_COURSE_STARTS = 15

# Age bands as the analysis endpoint writes them, matched to the race's own
# restriction text.
_AGE_BANDS = ("2yo", "3yo", "4yo", "5yo")


def _people(runners: list) -> list[tuple[str, str]]:
    """(name, type) for everyone with a live runner, de-duplicated."""
    seen: set[tuple[str, str]] = set()
    for r in runners or []:
        if r.get("scratched") or r.get("non_runner"):
            continue
        for field, kind in (("trainer", "trainer"), ("jockey", "jockey"), ("owner", "owner")):
            name = (r.get(field) or "").strip()
            if name and name.upper() != "SCRATCHED":
                seen.add((name, kind))
    return sorted(seen)


def _course_key(name: str) -> str:
    """"Belmont Park (USA)" and "Belmont Park" are the same track.

    The analysis endpoint suffixes a country on every non-GB course; the North
    America feed never does.
    """
    return re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name or "").strip().lower()


def _at_course(rows: list, course: str) -> dict | None:
    """A barn's or rider's record at today's track.

    Free: the courses facet is already fetched to build the headline record, so
    this is a lookup rather than another call. It is also the facet most worth
    having — a trainer who wins 12% overall and 26% at this one track is a
    different proposition today.
    """
    want = _course_key(course)
    if not want or not rows:
        return None
    for r in rows:
        if _course_key(r.get("course")) != want:
            continue
        runs = int(r.get("runners") or r.get("rides") or 0)
        if runs < MIN_COURSE_STARTS:
            return None
        return {"course": course, "starts": runs, "wins": int(r.get("1st") or 0),
                "win_rate": round(float(r.get("win_%") or 0), 4),
                "ae": round(float(r.get("a/e") or 0), 2)}
    return None


def _at_trip(payload: dict, race_furlongs: float) -> dict | None:
    """A person's record at today's kind of trip, not across every distance.

    A rider's mile figures say nothing about a five-furlong dash, and the
    overall number hides both.
    """
    rows = (payload or {}).get("distances") or []
    want = bucket_for(race_furlongs) if race_furlongs else None
    if not rows or not want:
        return None
    runs = wins = 0
    ae_num = 0.0
    for r in rows:
        f = furlongs_of(r.get("dist_f"))
        if f is None or bucket_for(f) != want:
            continue
        n = int(r.get("runners") or r.get("rides") or 0)
        runs += n
        wins += int(r.get("1st") or 0)
        ae_num += float(r.get("a/e") or 0) * n
    if runs < MIN_STARTS:
        return None
    return {"trip": want, "starts": runs, "wins": wins,
            "win_rate": round(wins / runs, 4), "ae": round(ae_num / runs, 2)}


def _combo(payload: dict, jockey_name: str) -> dict | None:
    """What this trainer and this rider have done together."""
    rows = (payload or {}).get("jockeys") or []
    want = {t for t in jockey_name.lower().replace(".", " ").split() if len(t) > 1}
    if not want:
        return None
    for r in rows:
        have = {t for t in (r.get("jockey") or "").lower().replace(".", " ").split() if len(t) > 1}
        if want <= have or have <= want:
            runs = int(r.get("runners") or 0)
            if runs < 10:  # a pairing needs a few goes before it means anything
                return None
            return {"starts": runs, "wins": int(r.get("1st") or 0),
                    "win_rate": round(float(r.get("win_%") or 0), 4),
                    "ae": round(float(r.get("a/e") or 0), 2)}
    return None


async def get_connections_form(runners: list, race_furlongs: float = 0.0,
                               course: str = "") -> dict[tuple[str, str], dict]:
    """Records keyed by (name, type): overall, at this track, at today's trip,
    and the trainer-rider pairing."""
    people = _people(runners)
    if not people:
        return {}
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(name: str, kind: str):
        async with gate:
            try:
                form = await racing_api.get_person_form(name, kind)
                if not form or form.get("starts", 0) < MIN_STARTS:
                    return (name, kind), None
                if course:
                    form["at_course"] = _at_course(form.get("courses") or [], course)
                if race_furlongs:
                    trip = await racing_api.get_person_facet(form["id"], kind, "distances")
                    form["at_trip"] = _at_trip(trip, race_furlongs)
                form.pop("courses", None)  # the rows themselves never reach the prompt
                return (name, kind), form
            except Exception:
                return (name, kind), None

    found = {k: v for k, v in await asyncio.gather(*(one(n, k) for n, k in people)) if v}

    # Trainer x jockey, for the pairings actually going to post today.
    async def pair(trainer_name, jockey_name):
        rec = found.get((trainer_name, "trainer"))
        if not rec:
            return None
        async with gate:
            payload = await racing_api.get_person_facet(rec["id"], "trainer", "jockeys")
        combo = _combo(payload, jockey_name)
        if combo:
            rec.setdefault("combos", {})[jockey_name] = combo

    pairs = {((r.get("trainer") or "").strip(), (r.get("jockey") or "").strip())
             for r in runners or []
             if not r.get("scratched") and r.get("trainer") and r.get("jockey")}
    await asyncio.gather(*(pair(t, j) for t, j in pairs))
    return found


def render_connections_block(runners: list, form: dict[tuple[str, str], dict]) -> str:
    """One line per runner whose trainer or jockey we have numbers for."""
    if not form:
        return ""
    lines = []
    for r in runners or []:
        if r.get("scratched") or r.get("non_runner"):
            continue
        parts = []
        trainer_name = (r.get("trainer") or "").strip()
        jockey_name = (r.get("jockey") or "").strip()
        for field, kind, label in (("trainer", "trainer", "Trn"), ("jockey", "jockey", "Jky"),
                                   ("owner", "owner", "Own")):
            name = (r.get(field) or "").strip()
            rec = form.get((name, kind))
            if not rec:
                continue
            line = (f"{label} {name}: {rec['win_rate']:.0%} win, {rec['itm_rate']:.0%} ITM "
                    f"({rec['starts']} starts), a/e {rec['ae']:.2f}, "
                    f"{rec['profit_per_unit']:+.2f}/unit")
            here = rec.get("at_course")
            if here:
                line += (f"; AT THIS TRACK {here['win_rate']:.0%} from {here['starts']}, "
                         f"a/e {here['ae']:.2f}")
            trip = rec.get("at_trip")
            if trip:
                line += (f"; at {trip['trip']} trips {trip['win_rate']:.0%} "
                         f"from {trip['starts']}, a/e {trip['ae']:.2f}")
            parts.append(line)
        combo = (form.get((trainer_name, "trainer")) or {}).get("combos", {}).get(jockey_name)
        if combo:
            parts.append(
                f"Together: {combo['win_rate']:.0%} from {combo['starts']} rides, "
                f"a/e {combo['ae']:.2f}"
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
        "- \"AT THIS TRACK\" is their record at today's course specifically. Weigh it "
        "above the overall figure: a barn that wins 12% overall and 26% here knows "
        "something about this track.\n"
        "- \"at sprint/middle/route trips\" is their record at today's kind of distance, "
        "which can differ sharply from the overall figure. \"Together\" is this exact "
        "trainer-and-rider pairing.\n"
        f"- Anyone with fewer than {MIN_STARTS} starts on file is left out rather than "
        "shown as a percentage off a handful of runs."
    )


async def get_connections_context(runners: list, race_furlongs: float = 0.0,
                                  course: str = "") -> str:
    """The block, ready to drop into a prompt. Never raises."""
    try:
        return render_connections_block(
            runners, await get_connections_form(runners, race_furlongs, course))
    except Exception as e:  # noqa: BLE001
        print(f"[connections] unavailable: {type(e).__name__}: {e}")
        return ""
