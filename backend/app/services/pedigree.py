"""
Sire and damsire form at today's trip, for the horses with no form of their own.

The system prompt has always told Secretariat that pedigree is "from general
knowledge only" — it had no numbers. The Pro analysis endpoints cover sires
well even though they only hold US stakes races, because a stallion's progeny
run everywhere and every one of those runs counts: Tapit comes back with 2,458
runners, Into Mischief 1,690, Gun Runner 560, each split by distance and class
with actual/expected attached.

Only first-time starters and lightly-raced horses get a lookup. That is where
pedigree decides anything, it keeps a card's worth of requests small, and it
avoids drowning a horse that has ten runs of its own in inherited numbers.
"""
import asyncio
import re

from app.services import racing_api

_CONCURRENCY = 4

# A stallion needs a real book behind a percentage. Below this we say nothing.
MIN_RUNNERS = 100

# Distance buckets in furlongs. A sire's mile figures say little about a horse
# going five, so progeny runs are matched to today's trip rather than averaged
# across every distance the stallion has ever had a runner at.
_BUCKETS = (
    ("sprint", 0.0, 6.5),
    ("middle", 6.5, 8.5),
    ("route", 8.5, 99.0),
)


def bucket_for(furlongs: float) -> str | None:
    for name, lo, hi in _BUCKETS:
        if lo <= furlongs < hi:
            return name
    return None


def furlongs_of(dist_f) -> float | None:
    """The feed writes distances as '8.5f', '1m½f' or a bare number."""
    if dist_f is None:
        return None
    try:
        return float(dist_f)
    except (TypeError, ValueError):
        pass
    m = re.match(r"^\s*([\d.]+)\s*f", str(dist_f))
    return float(m.group(1)) if m else None


def summarise_at_trip(payload: dict, race_furlongs: float) -> dict | None:
    """Progeny record at today's kind of trip, not across every distance."""
    rows = (payload or {}).get("distances") or []
    want = bucket_for(race_furlongs) if race_furlongs else None
    if not rows or not want:
        return None
    runners = wins = 0
    ae_num = 0.0
    for r in rows:
        f = furlongs_of(r.get("dist_f"))
        if f is None or bucket_for(f) != want:
            continue
        n = int(r.get("runners") or 0)
        runners += n
        wins += int(r.get("1st") or 0)
        ae_num += float(r.get("a/e") or 0) * n
    if runners < MIN_RUNNERS:
        return None
    return {
        "trip": want,
        "runners": runners,
        "wins": wins,
        "win_rate": round(wins / runners, 4),
        "ae": round(ae_num / runners, 2),
    }


async def _one_sire(name: str, kind: str, furlongs: float):
    ped_id = await racing_api.find_pedigree_id(name, kind)
    if not ped_id:
        return None
    try:
        payload = await racing_api.get_pedigree_analysis(ped_id, kind, "distances")
    except Exception:
        return None
    rec = summarise_at_trip(payload, furlongs)
    if rec:
        rec["name"] = name
    return rec


def _needs_pedigree(runner: dict, form_counts: dict[str, int]) -> bool:
    """First-time starters and horses with barely any record of their own."""
    if runner.get("scratched") or runner.get("non_runner"):
        return False
    key = (runner.get("horse_name") or "").strip().lower()
    return form_counts.get(key, 0) <= 1


async def get_pedigree_context(runners: list, race_furlongs: float,
                               form_counts: dict[str, int] | None = None) -> str:
    """Sire and damsire lines for the runners who need them. Never raises."""
    try:
        if not race_furlongs:
            return ""
        counts = form_counts or {}
        targets = [r for r in (runners or []) if _needs_pedigree(r, counts)]
        if not targets:
            return ""

        wanted: dict[tuple[str, str], None] = {}
        for r in targets:
            for field, kind in (("sire", "sires"), ("damsire", "damsires")):
                nm = (r.get(field) or "").strip()
                if nm:
                    wanted[(nm, kind)] = None

        gate = asyncio.Semaphore(_CONCURRENCY)

        async def one(nm, kind):
            async with gate:
                return (nm, kind), await _one_sire(nm, kind, race_furlongs)

        found = {k: v for k, v in await asyncio.gather(
            *(one(nm, kind) for nm, kind in wanted)) if v}

        lines = []
        for r in targets:
            parts = []
            for field, kind, label in (("sire", "sires", "Sire"), ("damsire", "damsires", "Damsire")):
                nm = (r.get(field) or "").strip()
                rec = found.get((nm, kind))
                if rec:
                    parts.append(
                        f"{label} {nm}: {rec['win_rate']:.0%} from {rec['runners']} "
                        f"progeny runs at this kind of trip, a/e {rec['ae']:.2f}"
                    )
            if parts:
                lines.append(f"#{r.get('number', '?')} {r.get('horse_name', '')}: " + " | ".join(parts))
        if not lines:
            return ""
        return (
            "\n\nPEDIGREE AT TODAY'S TRIP (first-time starters and lightly-raced only):\n"
            + "\n".join(lines)
            + "\n- Progeny runs at a similar distance to today, not the stallion's overall "
              "record. a/e above 1.00 means the progeny beat their prices at this trip.\n"
            f"- Stallions with fewer than {MIN_RUNNERS} progeny runs in the bucket are left "
            "out rather than quoted off a small book."
        )
    except Exception as e:  # noqa: BLE001
        print(f"[pedigree] unavailable: {type(e).__name__}: {e}")
        return ""
