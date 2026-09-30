"""
Real racing data for the Advisor, in place of scraping a web page for it.

The Advisor's live-racing path used web search: three fetches of bloodhorse or
drf, from which the model had to reconstruct a field. It is slow, it costs more
than the answer is worth, the pages are often a day stale, and the prompt has a
whole section begging the model not to invent entries — which is what you write
when the data underneath isn't dependable.

We already hold that data properly. `racing_api` wraps every endpoint on the
plan with Basic auth, a Redis cache, retries and a rate limiter, so exposing a
handful of those wrappers as tools gives the model the real field, the real
morning line and the real payoffs at the cost of a cache hit.

Why not the published MCP server at mcp.theracingapi.com: the Messages API
connector takes `type`, `url`, `name` and `authorization_token` and nothing
else, so the `X-RacingAPI-Username` / `X-RacingAPI-Password` headers it accepts
from a CLI cannot be sent, leaving OAuth as the only way in — an interactive
browser login plus token refresh. Even with a token, Anthropic's servers would
call the upstream directly, so every one of those calls would miss our cache,
skip our retries and go unseen by our rate limiter against a 5 req/sec plan.
The tools below reuse all three.
"""
import datetime
import json
import logging

from app.services import racing_api

log = logging.getLogger(__name__)

# Bounds on what any one tool may return. The model gets a usable field without
# a single call swallowing the context window.
MAX_RACES = 60
MAX_RUNNERS = 20
MAX_RESULTS = 40
MAX_HORSE_RUNS = 8

# Tool rounds per question. Four is enough to list a card, open a race, check a
# trainer and answer; it also caps the cost of a question that sends the model
# in circles.
MAX_TOOL_ROUNDS = 4


def _resolve_date(value: str | None) -> str:
    """'today' / 'tomorrow' / ISO date -> the ISO date racing_api expects."""
    today = datetime.date.today()
    v = (value or "today").strip().lower()
    if v in ("", "today"):
        return today.isoformat()
    if v == "tomorrow":
        return (today + datetime.timedelta(days=1)).isoformat()
    if v == "yesterday":
        return (today - datetime.timedelta(days=1)).isoformat()
    try:
        return datetime.date.fromisoformat(v).isoformat()
    except ValueError:
        return today.isoformat()


def race_number(race: dict) -> int | None:
    """The number on the card.

    The normalised race carries no explicit one: `race_name` is the stakes name
    where there is one and the string "Race 4" where there isn't, so the only
    dependable source is the suffix of the race_id ("ASD_1790640000000-4").
    """
    try:
        return int(str(race.get("race_id", "")).rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return None


# get_entries takes a race_number argument, which shadows the function above
# inside that body, so the helper gets a second name the parameter can't hide.
_num = race_number


def _race_title(race: dict) -> str:
    """The stakes name, or nothing when the feed only echoed the race number."""
    name = (race.get("race_name") or "").strip()
    return "" if name.lower().startswith("race ") else name


def _matches(track: str | None, course: str) -> bool:
    if not track:
        return True
    return track.strip().lower() in (course or "").lower()


# ── The tools ────────────────────────────────────────────────────────────────

async def list_races(date: str = "today", track: str = "") -> dict:
    """Every US race on a card, without the runners."""
    iso = _resolve_date(date)
    data = await racing_api.get_na_racecards_full(iso)
    races = []
    for r in data.get("racecards", []) or []:
        if not _matches(track, r.get("course", "")) or r.get("is_cancelled"):
            continue
        races.append({
            "track": r.get("course"),
            "race": race_number(r),
            "post_time": r.get("off_time") or r.get("off_dt"),
            "name": _race_title(r),
            "grade": r.get("pattern") or "",
            "distance": r.get("distance"),
            "surface": r.get("surface"),
            "condition": r.get("going"),
            "purse": r.get("prize"),
            "field_size": r.get("field_size"),
            "breed": r.get("breed") or "",
            "race_id": r.get("race_id"),
        })
    return {"date": iso, "races": races[:MAX_RACES], "total": len(races)}


async def get_entries(track: str, race_number: int = 0, date: str = "today",
                      race_id: str = "") -> dict:
    """The field for one race: post, morning line, live odds, connections."""
    iso = _resolve_date(date)
    data = await racing_api.get_na_racecards_full(iso)
    target = None
    for r in data.get("racecards", []) or []:
        if race_id and r.get("race_id") == race_id:
            target = r
            break
        if not _matches(track, r.get("course", "")):
            continue
        if race_number and str(_num(r)) != str(race_number):
            continue
        target = r
        break
    if not target:
        return {"error": f"No race found for {track or race_id} race {race_number} on {iso}"}

    runners = []
    for run in (target.get("runners") or [])[:MAX_RUNNERS]:
        runners.append({
            "number": run.get("number"),
            "horse": run.get("horse_name"),
            "post": run.get("post_position"),
            "jockey": run.get("jockey"),
            "trainer": run.get("trainer"),
            "morning_line": run.get("morning_line_odds"),
            "live_odds": run.get("live_odds"),
            "sire": run.get("sire"),
            "equipment": run.get("equipment"),
            "medication": run.get("medication"),
            "scratched": bool(run.get("scratched")),
        })
    return {
        "track": target.get("course"),
        "race": _num(target),
        "date": iso,
        "name": _race_title(target),
        "grade": target.get("pattern"),
        "distance": target.get("distance"),
        "surface": target.get("surface"),
        "condition": target.get("going"),
        "purse": target.get("prize"),
        "conditions": " ".join(x for x in [
            target.get("age_restriction"), target.get("sex_restriction"),
            target.get("race_restriction")] if x),
        "changes": target.get("changes") or [],
        "runners": runners,
    }


async def get_results(date: str = "today", track: str = "") -> dict:
    """Finishing order and official payoffs for races already run."""
    iso = _resolve_date(date)
    data = await racing_api.get_na_results_full(iso)
    out = []
    for r in (data.get("results") or [])[:MAX_RESULTS]:
        if not _matches(track, r.get("course", "")):
            continue
        finishers = [{
            "position": run.get("position"),
            "horse": run.get("horse_name"),
            "jockey": run.get("jockey"),
            "trainer": run.get("trainer"),
            "sp": run.get("sp"),
            "win_payoff": run.get("win_payoff"),
        } for run in (r.get("runners") or [])[:4]]
        out.append({
            "track": r.get("course"),
            "race": _num(r),
            "name": _race_title(r),
            "distance": r.get("distance"),
            "surface": r.get("surface"),
            "finishers": finishers,
        })
    return {"date": iso, "results": out, "total": len(out)}


async def get_person_record(name: str, person_type: str = "trainer") -> dict:
    """A trainer's or jockey's record over the plan's rolling twelve months.

    The same limit the profile page states applies here: the analysis dataset
    is group races and selected handicaps, so this is a record in stakes
    company and not an overall strike rate. The tool says so in its own reply,
    because the model quoting it as a career figure would be wrong.
    """
    kind = "jockey" if (person_type or "").lower().startswith("j") else "trainer"
    form = await racing_api.get_person_form(name, kind)
    if not form:
        return {"error": f"No record on file for {kind} {name}"}
    return {
        "name": name,
        "type": kind,
        "window": "rolling 12 months",
        "covers": "group races and selected handicaps only — stakes company, not an overall strike rate",
        "starts": form.get("starts"),
        "wins": form.get("wins"),
        "win_rate": form.get("win_rate"),
        "itm_rate": form.get("itm_rate"),
        "actual_over_expected": form.get("ae"),
        "profit_per_unit": form.get("profit_per_unit"),
    }


async def get_horse_record(name: str) -> dict:
    """A horse's recent runs."""
    found = await racing_api.search_horses(name)
    rows = (found or {}).get("search_results") or []
    if not rows:
        return {"error": f"No horse found named {name}"}
    horse = rows[0]
    hid = horse.get("id") or horse.get("horse_id")
    try:
        results = await racing_api.get_horse_results(hid, limit=MAX_HORSE_RUNS)
    except Exception:
        results = {}
    runs = []
    for r in (results.get("results") or [])[:MAX_HORSE_RUNS]:
        runs.append({
            "date": r.get("date"),
            "track": r.get("course"),
            "distance": r.get("dist"),
            "going": r.get("going"),
            "position": r.get("position"),
            "sp": r.get("sp"),
            "race": r.get("race_name"),
        })
    return {"horse": horse.get("name") or name, "sire": horse.get("sire"),
            "dam": horse.get("dam"), "runs": runs}


# ── Wiring for the Messages API ──────────────────────────────────────────────

_DATE_DESC = "'today', 'tomorrow', 'yesterday' or an ISO date like 2026-09-29. Defaults to today."

TOOLS = [
    {
        "name": "list_races",
        "description": (
            "Every US race carded on a given day: track, race number, post time, "
            "distance, surface, purse and field size. Use this first to find a race, "
            "then get_entries for the field. Covers North American tracks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": _DATE_DESC},
                "track": {"type": "string", "description": "Optional track name filter, e.g. 'Saratoga'."},
            },
        },
    },
    {
        "name": "get_entries",
        "description": (
            "The actual field for one race: program number, post position, horse, "
            "jockey, trainer, morning line, live odds where the pool is open, "
            "equipment and medication changes, and any scratches. Use this instead "
            "of guessing or recalling who is entered."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "track": {"type": "string", "description": "Track name, e.g. 'Churchill Downs'."},
                "race_number": {"type": "integer", "description": "Race number on the card."},
                "date": {"type": "string", "description": _DATE_DESC},
                "race_id": {"type": "string", "description": "Exact race id from list_races, if known."},
            },
            "required": ["track"],
        },
    },
    {
        "name": "get_results",
        "description": (
            "Finishing order and official payoffs for races already run: first four "
            "home with jockey, trainer, starting price and win payoff."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": _DATE_DESC},
                "track": {"type": "string", "description": "Optional track name filter."},
            },
        },
    },
    {
        "name": "get_person_record",
        "description": (
            "A trainer's or jockey's record over the last twelve months: starts, "
            "wins, win and in-the-money rate, actual-over-expected against their own "
            "prices, and profit on a flat unit. IMPORTANT: this dataset covers group "
            "races and selected handicaps, so it is a record in stakes company, not "
            "an overall strike rate. Say so if you quote it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full name, e.g. 'Chad Brown'."},
                "person_type": {"type": "string", "enum": ["trainer", "jockey"]},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_horse_record",
        "description": "A named horse's recent runs: date, track, distance, going, finishing position and starting price.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Horse name."}},
            "required": ["name"],
        },
    },
]

_DISPATCH = {
    "list_races": list_races,
    "get_entries": get_entries,
    "get_results": get_results,
    "get_person_record": get_person_record,
    "get_horse_record": get_horse_record,
}


async def run_tool(name: str, args: dict) -> str:
    """Call one tool and return its JSON reply.

    Never raises: a tool that blows up hands the model an error it can read and
    work around, which is better than losing the whole answer to one bad call.
    """
    fn = _DISPATCH.get(name)
    if not fn:
        return json.dumps({"error": f"No such tool: {name}"})
    try:
        result = await fn(**(args or {}))
    except TypeError as e:
        return json.dumps({"error": f"Bad arguments for {name}: {e}"})
    except Exception as e:  # noqa: BLE001
        log.warning("[advisor_tools] %s failed: %s: %s", name, type(e).__name__, e)
        return json.dumps({"error": f"{name} is unavailable right now"})
    return json.dumps(result, default=str)


TOOL_NAMES = frozenset(_DISPATCH)
