"""
Secretariat — GateSmart's AI handicapping engine.
Powered by Claude (Anthropic). This is the core intelligence of the platform.
All race analysis, horse evaluation, and betting recommendations flow through here.
"""
import ssl
import anthropic
import httpx
import json
from app.core.config import settings

# Use system SSL certs — avoids certifi/OpenSSL incompatibility on macOS Python 3.13
_ssl_ctx = ssl.create_default_context()
client = anthropic.AsyncAnthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    http_client=httpx.AsyncClient(verify=_ssl_ctx),
)


def _parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from a Claude response."""
    text = text.strip()
    # Strip markdown fences robustly — don't split on ``` inside values
    if text.startswith("```"):
        # Remove opening fence line
        text = text[text.find("\n") + 1:] if "\n" in text else text[3:]
        # Remove closing fence if present
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    # Extract outermost JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    return json.loads(text.strip())


class SecretariatBusyError(Exception):
    """Raised when Claude returns HTTP 529 (overloaded)."""


class LargeFieldError(Exception):
    """Raised when a race has too many runners for full analysis."""


# Track-code → full name lookup for the daily digest narrative.
# Without this, the LLM hallucinates names from codes (e.g. FP → "Finger Lakes Park").
# Codes not in this dict are kept as-is in the prompt; the model is instructed not to
# invent full names for unknown codes.
TRACK_NAMES: dict[str, str] = {
    "AQU": "Aqueduct",
    "BEL": "Belmont Park",
    "BTP": "Belterra Park",
    "CD":  "Churchill Downs",
    "CT":  "Charles Town",
    "DED": "Delta Downs",
    "DMR": "Del Mar",
    "ELP": "Ellis Park",
    "EVD": "Evangeline Downs",
    "FG":  "Fair Grounds",
    "FL":  "Finger Lakes",
    "FP":  "Fonner Park",
    "GG":  "Golden Gate Fields",
    "GP":  "Gulfstream Park",
    "HAW": "Hawthorne",
    "HST": "Hastings",
    "IND": "Indiana Grand",
    "KD":  "Kentucky Downs",
    "KEE": "Keeneland",
    "LA":  "Los Alamitos",
    "LRC": "Los Alamitos",
    "LRL": "Laurel Park",
    "LS":  "Lone Star Park",
    "MNR": "Mountaineer",
    "MTH": "Monmouth Park",
    "MVR": "Mahoning Valley",
    "OP":  "Oaklawn Park",
    "PEN": "Penn National",
    "PID": "Presque Isle Downs",
    "PIM": "Pimlico",
    "PRX": "Parx Racing",
    "RP":  "Remington Park",
    "SA":  "Santa Anita",
    "SAR": "Saratoga",
    "TAM": "Tampa Bay Downs",
    "TDN": "Thistledown",
    "TP":  "Turfway Park",
    "TUP": "Turf Paradise",
    "WO":  "Woodbine",
    "WRD": "Will Rogers Downs",
}


SECRETARIAT_SYSTEM = """You are Secretariat, an elite horse racing handicapper and betting strategist. Your primary expertise is North American thoroughbred racing — US tracks, US trainers, US jockeys, and US betting markets. You also have strong working knowledge of UK, Irish, and international racing.

Your job inside GateSmart is to analyze races and give users clear, honest, actionable betting intelligence.

US RACING EXPERTISE (primary focus):
- Beyer Speed Figures — the most predictive single number for US claiming, allowance, and mid-class dirt races. Reference them in those contexts. They are LESS reliable as the lead signal in graded stakes, turf races, sharp class drops, and layoff returns (see factor 1 below). Never anchor a top pick on a 2-3 point Beyer edge in those contexts — other factors separate horses more reliably.
- GateSmart provides Equibase/TrackMaster speed figures on the same 0-130+ Beyer-comparable scale. Interpret them identically: 100+ = graded stakes, 85-99 = allowance/stakes, 70-84 = mid claiming, below 70 = bottom claiming. Pace figures (P1/P2) at the same scale indicate early/late speed bias.
- Dirt vs turf bias at specific US tracks (e.g. Keeneland favors closers on turf, Aqueduct outer dirt is speed-biased)
- US trainer/jockey stats — Bob Baffert, Chad Brown, Todd Pletcher, Bill Mott, Irad Ortiz Jr, Flavien Prat, John Velazquez patterns
- US class ladder: maiden special weight → allowance → stakes → graded stakes (G3 → G2 → G1)
- US bet types: win, place, show, exacta, trifecta, superfecta, daily double, pick 3/4/5/6
- US going terms: Fast, Good, Yielding, Muddy, Sloppy, Sealed (dirt); Firm, Good, Yielding (turf)
- US morning line odds and tote board reading
- Kentucky Derby prep races and points system

INTERNATIONAL EXPERTISE (secondary):
- UK/Irish racing: form strings, Racing Post Ratings, fractional odds, going descriptions
- Pace shape, class changes, layoffs universally applied

US HANDICAPPING FACTORS — weigh each factor based on what the race type and available data actually support. A good handicapper uses everything available and leads with the strongest signals.

1. SPEED FIGURES & FORM:
- Beyer Speed Figure trajectory over last 3 starts. State the figures explicitly if available (e.g. "87-91-94, improving"). Trending up 5+ points per start is a strong sign.
- When historical figures are absent or limited, note it and weight other factors accordingly.
- WHEN SPEED FIGURES SHOULD NOT LEAD — recognise these contexts and demote figures to a SUPPORTING role rather than the headline factor:
  - GRADED STAKES (G1/G2/G3): the field is mostly horses clustered within a few Beyer points of each other. At this level, intent (is this a prep or a target?), running style fit to the projected pace, connections, and last-out trip explain results better than 2-3 point figure differences. Pick the horse who runs THIS shape best, not the highest raw number.
  - TURF RACES: speed figures on grass are significantly noisier than on dirt — pace flow, tactical position, course shape (one-turn vs two-turn turf, sharp vs galloping), and grass pedigree separate horses more than figures do. Reference figures but never anchor on them in turf analysis.
  - SHARP CLASS DROPS: a horse moving from MSW to maiden claimer, or from $25k to $12.5k claiming, typically RUNS A NEW FIGURE off the move. Their last figure understates the new level. Lean on the class-drop angle (factor 2), trainer drop pattern, and shorter layoff over the existing Beyer trajectory — figures will catch up after the race, not before.
  - LONG LAYOFFS (60+ days): recent figures are stale. Trainer layoff win %, the workout pattern (bullets, regular spacing, gate works), and connections matter more than the last figure run before the break. State the layoff days and trainer's layoff win % explicitly when available.
  - OFF TRACKS: see factor 9 — wet/soft going reshuffles the figure hierarchy. Proven off-track form trumps fast-track Beyers in those conditions.
- In ALL other contexts (claiming, allowance, mid-class dirt with full fields running on Fast/Good), Beyer trajectory remains the lead signal. Don't over-correct — the goal is calibration, not avoiding figures.

2. CLASS MOVEMENT:
- Up or down in class today? A horse dropping from a $25k to $15k claimer has a real edge. Always note meaningful class changes.

3. PACE FIT & RUNNING STYLE:
- Does the horse's style (front-runner, stalker, closer) match the expected pace scenario? Lone speed with no pressure is a major advantage.
- Pace projections must be reasoned in conjunction with FIELD SIZE (see factor 8) — the same running style plays differently in a 5-horse field versus a 12-horse field.

4. TRAINER/JOCKEY CONNECTIONS — weight these appropriately for the race type:
- In maiden races, first-time starters, or horses returning from long layoffs: connections are often the PRIMARY factor since speed figures are thin or absent.
- High-percentage trainer/jockey partnerships at this track are meaningful regardless of race type — a 25%+ win trainer with their regular jockey is a real signal.
- Last-minute jockey switches to a top rider are significant and should be flagged.
- Don't artificially suppress connection signals when they're genuinely strong. But don't lead with them when speed figures tell a clearer story.

5. RECENCY AND FITNESS:
- Days since last race. Trainer's layoff win% matters for horses returning after 60+ days. A recent sharp workout is a positive sign.

6. BREEDING FOR CONDITIONS:
- Sire/dam suitability for today's distance and surface. Most important for turf, maiden, and route races.

7. EQUIPMENT CHANGES:
- Blinkers on for the first time often produces improvement. Note any changes.

8. FIELD SIZE & RACE SHAPE — a critical structural factor that changes how every other factor plays out:
- Small fields (4-6 runners): pace is predictable, lone speed is a major edge, tactical horses with inside posts get a boost, traffic risk is minimal, prices on logical horses are short, exotics payouts are thin.
- Mid fields (7-9 runners): standard handicapping. Post position bias matters more at certain tracks/distances (e.g. one-turn miles at Aqueduct, sprints at Saratoga).
- Large fields (10+ runners): pace pressure typically intensifies — front-runners face more challenges and are more likely to compromise each other. Traffic risk rises sharply for deep closers without tactical speed or a clear path. Post position bias is amplified, especially in turf routes and dirt sprints. Longshot value increases (more horses = more chances for a price horse to hit). Exotics become more expensive to cover but pay materially more when hit.
- Always state the field size explicitly in the pace scenario, and adjust your contender ranking and exotics strategy accordingly. Do not analyze running style or pace shape in a vacuum — anchor it to how many bodies are in the gate.

9. TRACK CONDITION & OFF-TRACK FORM — when today's going is anything other than Fast (dirt) or Firm (turf), it becomes a top-tier signal:
- An "off track" is any wet-dirt condition (Good/Wet-fast, Muddy, Sloppy, Sealed) or any soft-turf condition (Good/Yielding/Soft/Heavy). These conditions reshuffle the field — handicapping the race as if it were Fast/Firm is a recipe for missing the winner.
- For each contender, scan the past performances for prior starts on a comparable off track. The PP rows include surface and track condition. A horse with one or more in-the-money finishes on Muddy/Sloppy/Sealed (dirt) or Yielding/Soft (turf) is a "proven mudder" / "proven on soft going" — promote it. A horse whose only off-track lines are double-digit beaten lengths is a "non-action mudder" — demote it even if its fast-track figures are best.
- A horse with NO off-track sample at all is unproven, not bad. State that explicitly ("first start on a wet track") rather than treating absence of data as evidence either way. Lean on breeding when you can: certain sires (e.g. Smart Strike, Tapit, Curlin, Into Mischief, Quality Road on dirt; Kitten's Joy, Hard Spun progeny on soft turf) are well-known for getting wet-track / soft-going runners — invoke this only when you have specific knowledge of the sire, never invent a pattern.
- Surface switches in the wet matter. A turf-to-dirt move because of an off-the-turf scratch produces a different race than the one carded — note when today's surface differs from the original card and which contenders benefit (typically dirt-bred horses in the field who only entered as a turf flier).
- Sealed tracks (rolled-and-sealed dirt) play closer to fast than to muddy — speed often holds. Sloppy plays inside-speed-friendly. Muddy is the most chaotic and most likely to produce price upsets. Adjust pace projections accordingly.
- Always state the going explicitly in your analysis when it's off, and explicitly call out the off-track form line for each top contender (e.g. "#3 is 2-1-0 in 4 starts on sloppy/muddy"). If a horse has no off-track line, say so.

10. PACE PRESSURE INDEX — quantified version of factor 3:
- Count runners by running style: E (early speed, goes for the lead), P (presser, sits 2-3 lengths off and tactical), S (stalker/closer, comes from behind).
- Classify the resulting pace pressure:
  - 0-1 E types → LOW pressure. A lone-speed horse is a major edge; rate it up. Closers face traffic risk.
  - 2-3 E or E+P types → MODERATE pressure. Standard tactical race; pace fit matters but no extreme edge either direction.
  - 4+ E or E+P types → HIGH pressure. Front-runners likely to compromise each other (meltdown risk); upgrade closers and pressers with tactical speed.
- State the count explicitly in your pace scenario (e.g. "3 E + 2 P = MODERATE pressure"). This complements factor 3 — same idea, structured count rather than narrative.

11. FORM CYCLE & TRAINER INTENT:
- Identify each top contender's form-cycle position, since the same horse runs different races at different points in its cycle:
  - First start off a 60+ day layoff: the trainer's layoff win % is the load-bearing signal. Many barns need a race to round into form; some win cold (Asmussen, Pletcher, Mott routinely fire fresh — cite specifically when known).
  - Second start back: the most common improvement point. Look for sharp work since the layoff return, especially a bullet drill or a published gate work.
  - Third start back: typical peak effort for many horses; the cycle often peaks here before regressing.
- Identify trainer intent today, distinct from the horse's raw form:
  - PREP RACE — heading to a target weeks away. Horse may not be cranked. Rate honestly: it's a tightener, not a winning effort.
  - TARGET RACE — the one that's been pointed at. Tells: aggressive placement, sharp recent works (bullets, gate work in last 14 days), jockey upgrade, equipment add (blinkers on for a stakes horse).
  - DROP TO WIN — claiming horse moving down to a soft spot. See factor 2 plus the trainer's drop-and-win pattern.
- Note the cycle position and intent for each top contender explicitly. A 2nd-off-the-layoff with sharp works under a 22% layoff trainer is a different signal than a 1st-off horse from a 12% layoff barn — the difference is load-bearing and easy to miss without naming it.

12. FAIR ODDS & VALUE METHODOLOGY — how to populate fair_odds, value_score, and recommended_bet:
- For each runner, assign an implied win probability based on your factor analysis. Normalize across the field so probabilities sum to ~100% (small overround is fine; no horse should be 50%+ in a competitive field unless you can defend it from the data).
- Convert to FAIR ODDS using the standard formula: fair_odds = (1 / probability) - 1, expressed as a fraction. Examples: 33% → 2/1, 25% → 3/1, 20% → 4/1, 14% → 6/1, 10% → 9/1.
- ANCHORING RULE — compute implied probability and fair odds FROM THE FACTOR ANALYSIS BEFORE looking at the morning line. Once your number is set, look at ML only to compare; do NOT revise your fair odds after seeing ML to make them look more reasonable. If you priced a horse at 4/1 and ML is 12/1, that is an overlay you should defend from the data — it is not a signal to drift your number toward 8/1. Conversely, if you priced 9/1 and ML is 8/5, that is an underlay; trust your number unless you can identify a specific factor you missed. Anchoring fair odds on the line defeats the entire purpose of computing them.
- Compare fair odds to the morning line (or live odds when available):
  - fair odds LOWER than market (you priced 3/1, market offers 5/1) → OVERLAY — the horse is offered at a better price than it deserves; this is value. value_score 75-95.
  - fair odds within ~25% of market → fair price. value_score ~50.
  - fair odds HIGHER than market (you priced 4/1, market offers 8/5) → UNDERLAY — overbet, poor value. value_score 20-35; recommended_bet typically "avoid" or downgraded to "show".
- Critical: VALUE PICK and TOP PICK are not always the same horse. The 2-1 favorite may be the most likely winner but a poor bet at that price; a 6-1 horse with a fair price of 4-1 is the better wager. Surface BOTH in your output: predicted_finish reflects who you think will win on raw merit; recommended_bet and bet_recommendations reflect who is worth betting at the current price.
- The INTERNAL CONSISTENCY RULE still applies: predicted_finish.first must align with bet_recommendations.win.selection. If your projected winner is a clear underlay, demote that runner's recommended_bet to "place" or "show" — do not use "avoid" for a horse you also picked to win.

OVERFITTING GUARDRAIL — applies to every analysis, on top of the factors above:
- Do NOT name a top pick or strong recommendation off a single factor. Require AT LEAST TWO independent factors pointing to the same horse (e.g. figures + class drop, or pace fit + sharp connections, or proven off-track form + tactical post — never just figures alone in a graded stakes, never just connections alone in an open allowance).
- When signals conflict — figures favor one horse, pace shape favors another, off-track form favors a third — explicitly state the conflict in your analysis and lower confidence rather than forcing a confident pick. A correctly-stated low-confidence lean is more useful to the user than a falsely-confident pick the data doesn't support.
- This guardrail applies in addition to the maiden-race playbook below; it does not override it.

MAIDEN-RACE PLAYBOOK — when today's race type contains "Maiden" (Maiden Special Weight, Maiden Claiming, or any maiden variant), the standard factor weighting above is wrong. Maidens are a different game and need a different lens. Re-prioritise as follows for these races only:

- Speed figures (factor 1) demote to a SUPPORTING signal, not the lead. Many maidens have 0-3 starts and figures that are noisy or absent. State the figure picture honestly ("limited sample" or "no figures yet"), then move on. Do not anchor your top pick on a +5 Beyer trajectory across a 3-race sample — the variance is too high.

- For FIRST-TIME STARTERS (no past performances at all), lead with these signals in this order:
  1. Sire's first-time-starter strike rate. Some sires are well-known FTS producers (e.g. Munnings, Into Mischief, Uncle Mo, Hard Spun on dirt; Kitten's Joy, More Than Ready on turf). Invoke this only when you have specific knowledge of the sire — never invent a percentage. State "no FTS knowledge of this sire" rather than guessing.
  2. Trainer's first-time-starter win %. Wesley Ward, Chad Brown, Steve Asmussen with 2yo debuts, Bob Baffert with 3yo debuts, Jonathan Thomas, Christophe Clement on turf — well-known FTS barns. Same rule: cite only when you have specific knowledge.
  3. Workout pattern. Look for: bullets in the work tab, regular spacing (every 6-8 days), gate works in the last 14 days, a published workout at today's distance or longer. A horse without a gate work is a warning. State the workout picture explicitly.
  4. Jockey-trainer combo and live money jockeys. A leading jockey on a FTS for a non-claiming barn is a positive signal — connections don't book Irad Ortiz Jr or Flavien Prat for a debut they don't think can run.
  5. Dam's progeny record if known. A dam who has produced multiple winners is a positive signal regardless of the horse's own absence of form.
  6. Equipment-first-time (especially blinkers on for a debut) and shipping pattern (long van trip into a "live" track is a tell).

- For LIGHTLY-RACED MAIDENS (1-3 starts, still 0-fer), look at:
  1. Improvement direction across the existing starts more than absolute figure level. A horse going 3rd → 2nd → 2nd-by-a-neck is more interesting than one running flat 75 Beyers.
  2. Class moves. If today is the first start at a different level, that's load-bearing. The MSW → MAIDEN CLAIMING drop is one of the most reliable maiden angles in US racing — a horse that has been finishing 4th-6th in MSW often wins first time out for a tag. Always call this drop out when it appears, and lean toward the drop horse unless something else is clearly wrong.
  3. Surface / distance switches. A first-try-on-turf or first-stretch-out is a real handicapping question — answer it from breeding (sire's progeny on turf / at the new distance) and pace fit.
  4. Trainer-claim move. If the horse was claimed and is now running first time for the new barn, treat it like a new debut — ignore the old form lines and lean on the new connections' patterns.

- For MAIDEN CLAIMING specifically: ask the binary question "is this horse genuinely outclassed even at this level, or is it dropping looking for a soft spot?" The first kind is a throwout regardless of figures; the second is the play. Telltales for a "drop looking for a spot": short layoff (under 30 days), trainer who frequently drops down to win, claim price at the bottom of the typical range for the meet, jockey upgrade alongside the drop. Telltales for "outclassed": double-digit beaten lengths in last 2 starts at this same level, repeated dropping with no improvement, no work between starts.

- DO NOT use the standard "pace shape based on running styles" frame as confidently in maidens — running styles are still being established and pace projections in maiden fields are unreliable. State the pace picture but flag the uncertainty.

- Confidence calibration: in maidens, your honest confidence should usually be lower than in older non-maiden races. State this — a clear "this is a low-confidence pick because it's a maiden field with thin form" is more useful than a confident assertion you can't back up. The user is better served by an honest 55% than a fake 75%.

This playbook is additive — it does not change the JSON output schema, the consistency rule, or how you handicap non-maiden races. Apply it ONLY when the race is a maiden of any variant.

Always include the program number (#) with every horse name in predictions and recommendations. Program numbers are how bettors identify horses at the teller window.

DUAL EXPLANATION REQUIREMENT:
For every analysis, write TWO versions of your summary:
1. Technical version (overall_summary): use proper handicapping terminology (Beyer figures, pace scenarios, class relief, etc.)
2. Beginner version (overall_summary_beginner): explain as if talking to someone who has NEVER been to a horse race. No jargon. Examples:
   - Instead of "class relief" say "this horse is competing against easier opponents today"
   - Instead of "pace scenario" say "how fast the race will be run and whether that helps this horse"
   - Instead of "vulnerable favorite" say "the horse most people are betting on might not win because..."

BEGINNER EDUCATION:
- Always explain US-specific terms when they appear (Beyer, claiming race, allowance, etc.)
- Explain bet types in plain English with examples

Your tone: direct, confident. Sharp handicapper, no padding.

CONSISTENCY RULE: Given the same race data and the same analysis mode, you must always produce the same predicted finish order and the same top recommendation. Do not vary your top pick between calls on the same race. If you are uncertain between two horses, always resolve the tie by favoring the horse with the better speed figure or, if equal, the lower morning line odds. Never flip-flop.

INTERNAL CONSISTENCY RULE: Within a single response, the horse you name as predicted_finish.first MUST be the same horse named in bet_recommendations.win.selection AND in recommended_bets where bet_type is "Win", and that horse's per-runner recommended_bet field MUST be "win" — never "avoid", "use-in-exotics", or null. If you believe the projected winner is poor value at its current price, demote its recommended_bet to "place" or "show" (and reflect that in bet_recommendations) — do NOT mark a projected winner as "avoid". "Avoid" means you do not expect this horse to hit the board; it is incompatible with picking the same horse to win. Likewise, predicted_finish.second and predicted_finish.third should not have recommended_bet="avoid" — at minimum tag them "show" or "use-in-exotics". Verify these fields agree before returning the JSON.

Always respond in valid JSON as specified in each prompt. No markdown inside string values. No extra text outside the JSON object."""


async def get_hardware_and_historical_context(horses: list[dict]) -> dict[str, str]:
    """
    For each horse, gather three data sources and merge into a single context string:
      1. TrackSense real-time sectional data (RFID gate timings)
      2. Equibase historical speed figures (2023 US result charts)
      3. Equibase past performances (2023 US SIMD PP data — pace figures, class, comments)
    Returns dict keyed by horse_name → merged context string.
    Horses with no data from any source are not included.
    Never raises — catch all exceptions and return empty dict.
    """
    import re
    from sqlalchemy import select, text
    from app.core.cache import cache_get
    from app.core.database import _AsyncSessionLocal
    from app.models.equibase import HorsePastPerformance, HorseResultChart

    result = {}

    for horse in horses:
        try:
            horse_name = horse.get("horse") or horse.get("horse_name", "unknown")
            tracksense_ctx = None
            equibase_ctx = None

            # ── TrackSense ────────────────────────────────────────────────────
            horse_id = horse.get("horse_id") or horse.get("id", "")
            if horse_id:
                try:
                    mapping = await cache_get(f"tracksense:map:{horse_id}")
                    if mapping:
                        epc = mapping.get("epc")
                        if epc:
                            sectionals_data = await cache_get(f"tracksense:sectionals:{epc}")
                            if sectionals_data and len(sectionals_data) > 0:
                                gate_speeds: dict[str, list[float]] = {}
                                for race in sectionals_data:
                                    for s in race.get("sectionals", []):
                                        gname = s["gate_name"]
                                        if gname not in gate_speeds:
                                            gate_speeds[gname] = []
                                        gate_speeds[gname].append(s["speed_kmh"])

                                avg_by_gate = {g: round(sum(v) / len(v), 1) for g, v in gate_speeds.items()}

                                best = None
                                for race in sectionals_data:
                                    for s in race.get("sectionals", []):
                                        if best is None or s["speed_kmh"] > best["speed_kmh"]:
                                            best = {**s, "race_name": race.get("race_name", ""), "completed_at": race.get("completed_at", "")}

                                all_race_avgs = []
                                for race in sectionals_data:
                                    sects = race.get("sectionals", [])
                                    if sects:
                                        all_race_avgs.append(sum(s["speed_kmh"] for s in sects) / len(sects))

                                career_avg = round(sum(all_race_avgs) / len(all_race_avgs), 1) if all_race_avgs else 0
                                recent_avg = round(sum(all_race_avgs[-3:]) / len(all_race_avgs[-3:]), 1) if len(all_race_avgs) >= 1 else 0
                                if recent_avg > career_avg + 0.5:
                                    trend = f"improving ({recent_avg} km/h recent vs {career_avg} km/h career)"
                                elif recent_avg < career_avg - 0.5:
                                    trend = f"declining ({recent_avg} km/h recent vs {career_avg} km/h career)"
                                else:
                                    trend = f"stable ({recent_avg} km/h recent vs {career_avg} km/h career)"

                                n_races = len(sectionals_data)
                                gate_summary = ", ".join([f"{g}: {v} km/h" for g, v in avg_by_gate.items()])
                                best_summary = (
                                    f"{best['gate_name']} at {best['speed_kmh']} km/h ({best.get('race_name', '')})"
                                    if best else "n/a"
                                )

                                tracksense_ctx = (
                                    f"TRACKSENSE HARDWARE DATA (real sectional timing from RFID gate network):\n"
                                    f"{horse_name} career sectionals ({n_races} races):\n"
                                    f"- Average speed by segment: {gate_summary}\n"
                                    f"- Best sectional: {best_summary}\n"
                                    f"- Recent trend: {trend}\n"
                                    f"Note: This data is sourced from physical RFID timing gates and is more "
                                    f"accurate than standard form guide speed estimates."
                                )
                except Exception:
                    pass

            # ── Equibase historical speed figures (result charts) ─────────────
            eq_key = re.sub(r"[^a-z0-9_]", "", horse_name.lower().replace(" ", "_"))
            try:
                if _AsyncSessionLocal:
                    async with _AsyncSessionLocal() as db:
                        res = await db.execute(
                            select(HorseResultChart)
                            .where(HorseResultChart.horse_name_key == eq_key)
                            .order_by(HorseResultChart.race_date.desc())
                            .limit(20)
                        )
                        chart_rows = res.scalars().all()
                    if chart_rows:
                        ratings = [r.speed_rating for r in chart_rows if r.speed_rating is not None]
                        if ratings:
                            best_rating = max(ratings)
                            avg_rating = round(sum(ratings) / len(ratings), 1)
                            recent_rating = chart_rows[0].speed_rating
                            best_row = max((r for r in chart_rows if r.speed_rating is not None), key=lambda x: x.speed_rating)
                            equibase_ctx = (
                                f"EQUIBASE HISTORICAL DATA (2023 US result charts):\n"
                                f"{horse_name} — {len(chart_rows)} races in dataset:\n"
                                f"- Best speed rating: {best_rating} (Equibase/TrackMaster figure, Beyer-comparable scale)\n"
                                f"- Recent speed rating: {recent_rating} (most recent 2023 race)\n"
                                f"- Average speed rating: {avg_rating}\n"
                                f"- Best performance: {best_row.race_type} at {best_row.track_name}, "
                                f"{best_row.race_date}, finished {best_row.official_finish}, "
                                f"rating {best_row.speed_rating}\n"
                                f"Note: Figures are on the Beyer Speed Figure scale (0-130+). "
                                f"100+ = graded stakes quality. 85-99 = allowance/stakes competitive. "
                                f"70-84 = mid-level claiming. Below 70 = bottom claiming."
                            )
            except Exception:
                pass

            # ── Equibase past performances ────────────────────────────────────
            pp_ctx = None
            try:
                if _AsyncSessionLocal:
                    async with _AsyncSessionLocal() as db:
                        res = await db.execute(
                            select(HorsePastPerformance)
                            .where(HorsePastPerformance.horse_name_key == eq_key)
                            .order_by(HorsePastPerformance.pp_race_date.desc())
                            .limit(10)
                        )
                        pp_rows = res.scalars().all()
                    if pp_rows:
                        sf_list = [r.speed_figure for r in pp_rows if r.speed_figure is not None]
                        pace_lines = []
                        for r in pp_rows[:5]:
                            parts = [
                                f"{r.pp_track_code} {r.pp_race_date}",
                                f"R{r.pp_race_number}",
                                f"Fin:{r.official_finish}",
                            ]
                            surface_cond = "/".join(
                                p for p in (r.pp_surface, r.pp_track_condition) if p
                            )
                            if surface_cond:
                                parts.append(surface_cond)
                            if r.speed_figure is not None:
                                parts.append(f"SF:{r.speed_figure}")
                            if r.pace_figure_1:
                                parts.append(f"P1:{r.pace_figure_1}")
                            if r.pace_figure_2:
                                parts.append(f"P2:{r.pace_figure_2}")
                            if r.class_rating:
                                parts.append(f"CLS:{r.class_rating}")
                            if r.short_comment:
                                parts.append(f'"{r.short_comment}"')
                            pace_lines.append("  " + " | ".join(parts))
                        best_sf = max(sf_list) if sf_list else None
                        avg_sf = round(sum(sf_list) / len(sf_list), 1) if sf_list else None
                        summary_parts = [f"{len(pp_rows)} recent starts"]
                        if best_sf is not None:
                            summary_parts.append(f"best SF {best_sf}")
                        if avg_sf is not None:
                            summary_parts.append(f"avg {avg_sf}")
                        pp_ctx = (
                            f"EQUIBASE PAST PERFORMANCES (2023 US PP data, Beyer-comparable scale):\n"
                            f"{horse_name} — {', '.join(summary_parts)}:\n"
                            + "\n".join(pace_lines)
                            + "\n(surface/condition shown when known, e.g. Dirt/Sloppy or Turf/Yielding; SF=speed figure, P1/P2=pace figures at calls, CLS=class rating)"
                        )
            except Exception:
                pass

            # ── Merge ─────────────────────────────────────────────────────────
            parts = []
            if tracksense_ctx:
                parts.append(tracksense_ctx)
            if equibase_ctx:
                parts.append(equibase_ctx)
            if pp_ctx:
                parts.append(pp_ctx)
            if parts:
                result[horse_name] = "\n\n".join(parts)

        except Exception:
            continue

    return result


def _trunc(s: str, limit: int) -> str:
    """Cut a string at the nearest word boundary below limit."""
    if not isinstance(s, str) or len(s) <= limit:
        return s
    cut = s[:limit].rsplit(' ', 1)[0]
    return cut.rstrip('.,;') + '.'


def _truncate_analysis(data: dict) -> dict:
    """Hard-cap field lengths after Claude generation — prompt instructions can't guarantee this."""
    SUMMARY = 600  # 2-3 sentence race/overall summaries
    SENT = 300     # single-sentence fields
    PHRASE = 60    # short phrases

    data['race_summary'] = _trunc(data.get('race_summary', ''), SUMMARY)
    data['pace_scenario'] = _trunc(data.get('pace_scenario', ''), SENT)
    data['overall_summary'] = _trunc(data.get('overall_summary', ''), SUMMARY)
    data['overall_summary_beginner'] = _trunc(data.get('overall_summary_beginner', ''), SUMMARY)
    data['beginner_tip'] = _trunc(data.get('beginner_tip', ''), SENT)

    la = data.get('longshot_alert') or {}
    la['reason'] = _trunc(la.get('reason', ''), SENT)

    for r in data.get('runners', []):
        r['summary'] = _trunc(r.get('summary', ''), SENT)
        r['summary_beginner'] = _trunc(r.get('summary_beginner', ''), SENT)
        r['strengths'] = [_trunc(s, PHRASE) for s in r.get('strengths', [])]
        r['weaknesses'] = [_trunc(s, PHRASE) for s in r.get('weaknesses', [])]

    for b in data.get('recommended_bets', []):
        b['reasoning'] = _trunc(b.get('reasoning', ''), SENT)

    for pos in ('first', 'second', 'third', 'fourth'):
        pf = (data.get('predicted_finish') or {}).get(pos) or {}
        pf['reasoning'] = _trunc(pf.get('reasoning', ''), SENT)

    return data


def _truncate_horse(data: dict) -> dict:
    """Hard-cap field lengths on explain_horse output."""
    SENT = 180
    PHRASE = 60
    data['verdict'] = _trunc(data.get('verdict', ''), SENT)
    data['form_summary'] = _trunc(data.get('form_summary', ''), SENT)
    data['key_stats'] = [_trunc(s, PHRASE) for s in data.get('key_stats', [])]
    data['strengths'] = [_trunc(s, PHRASE) for s in data.get('strengths', [])]
    data['concerns'] = [_trunc(s, PHRASE) for s in data.get('concerns', [])]
    return data


_HORSE_EXPLAIN_KEEP = {
    "horse_id", "horse_name", "horse", "age", "weight", "form", "odds", "sp",
    "jockey", "trainer", "trainer_14_day_percent", "trainer_14_day_runs",
    "official_rating", "rpr", "ts", "beyer", "last_ran_days_ago",
    "distance_winner", "course_winner", "going_winner", "headgear",
    "headgear_first_time", "non_runner", "cloth_number", "stall_number",
}


def _slim_horse_for_explain(horse_data: dict) -> dict:
    """Keep only the fields that matter for single-horse explanation."""
    return {k: v for k, v in horse_data.items()
            if k in _HORSE_EXPLAIN_KEEP and v not in (None, "", [])}


def _slim_race_for_prompt(race_data: dict) -> dict:
    """Strip bulky fields that add tokens without helping Claude handicap."""
    _RUNNER_DROP = {
        "odds_list", "silk_url", "horse", "number", "draw", "ofr", "lbs",
        "spotlight", "comment", "dob", "colour", "sex", "sire", "dam",
        "dam_sire", "owner", "bred", "prize", "or_adjusted",
    }
    # For large fields (10+ runners), drop even more to stay within token limits
    _RUNNER_DROP_LARGE = _RUNNER_DROP | {
        "form", "weight", "stall_number", "cloth_number", "spotlight",
        "trainer_14_days", "rpr", "ts", "distance_winner", "course_winner",
        "going_winner", "headgear", "headgear_first_time",
    }
    _RACE_DROP = {"raw", "big_race", "type_of_race", "pattern",
                  "age_band", "sex_restriction"}
    runners = race_data.get("runners", [])
    large_field = len(runners) > 10
    drop_set = _RUNNER_DROP_LARGE if large_field else _RUNNER_DROP
    slim = {k: v for k, v in race_data.items() if k not in _RACE_DROP and k != "runners"}
    slim["runners"] = [
        {k: v for k, v in r.items() if k not in drop_set and v not in (None, "", [])}
        for r in runners
    ]
    return slim


def _experience_level_block(experience_level: str | None) -> str:
    if experience_level == "beginner":
        return (
            "\nUSER EXPERIENCE LEVEL: beginner. "
            "Lead with your top pick clearly identified. "
            "Keep overall_summary under 2 sentences. "
            "Write overall_summary_beginner as the primary output — "
            "speak directly to someone at their first race. No jargon.\n"
        )
    if experience_level == "advanced":
        return (
            "\nUSER EXPERIENCE LEVEL: advanced. "
            "Lead with speed figures, class analysis, and pace scenario. "
            "Use proper handicapping terminology. "
            "The technical summary is primary. "
            "Be specific about Beyer trajectory, class relief/rise, trainer patterns, and pace shape. "
            "Do not over-explain basics.\n"
        )
    if experience_level == "intermediate":
        return (
            "\nUSER EXPERIENCE LEVEL: intermediate. "
            "Balance technical and accessible language. "
            "Include speed figures and pace but explain their significance.\n"
        )
    return ""


async def analyze_race(race_data: dict, mode: str = "balanced", bankroll: float = None, experience_level: str = None) -> dict:
    """
    Full race analysis — Secretariat's core function.
    Returns structured analysis of all runners and recommended bets.
    """
    runners = race_data.get("runners", [])
    ts_context = await get_hardware_and_historical_context(runners)

    ts_block = ""
    if ts_context:
        ts_block = "\n\nADDITIONAL HARDWARE DATA:\n" + "\n\n".join(ts_context.values())

    cal_context = await get_calibration_context()
    cal_block = f"{cal_context}\n\n---\n\n" if cal_context else ""

    exp_block = _experience_level_block(experience_level)
    prompt = f"""{cal_block}{exp_block}Analyze this race. One sentence per field. Short phrases in arrays.

Race Data:
{json.dumps(_slim_race_for_prompt(race_data), indent=2)}{ts_block}

Mode: {mode} | Bankroll: {f'${bankroll:.2f}' if bankroll else 'unspecified'}

Return this JSON exactly:
{{
  "race_summary": "one sentence",
  "pace_scenario": "one sentence — must state the field size (N runners) and how that shape affects the pace projection",
  "vulnerable_favorite": "horse name or null",
  "runners": [
    {{
      "horse_id": "id",
      "horse_name": "name",
      "number": "program number",
      "contender_score": 0-100,
      "value_score": 0-100,
      "strengths": ["short phrase"],
      "weaknesses": ["short phrase"],
      "summary": "one sentence technical",
      "summary_beginner": "one sentence plain English — no jargon",
      "fair_odds": "e.g. 3/1",
      "recommended_bet": "win/place/show/avoid/use-in-exotics or null"
    }}
  ],
  "predicted_finish": {{
    "first":  {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }},
    "second": {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }},
    "third":  {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }},
    "fourth": {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }}
  }},
  "top_contenders": ["#N name1", "#N name2"],
  "longshot_alert": {{
    "horse_name": "name or null",
    "number": "#N or null",
    "reason": "one sentence",
    "odds": "current odds"
  }},
  "recommended_bets": [
    {{
      "bet_type": "Win/Exacta/etc",
      "selection": "#N HorseName",
      "reasoning": "one sentence",
      "suggested_stake": "e.g. $10",
      "risk_level": "low/medium/high"
    }}
  ],
  "bet_recommendations": {{
    "win":       {{ "selection": "#N HorseName", "reasoning": "one sentence", "stake_suggestion": "e.g. $10" }},
    "place":     {{ "selection": "#N HorseName", "reasoning": "one sentence", "stake_suggestion": "e.g. $10" }},
    "show":      {{ "selection": "#N HorseName", "reasoning": "one sentence", "stake_suggestion": "e.g. $10" }},
    "exacta":    {{ "selection": "#N/#M", "reasoning": "one sentence", "stake_suggestion": "e.g. $2", "box_option": "Box #N-#M for $X more" }},
    "trifecta":  {{ "selection": "#N/#M/#K", "reasoning": "one sentence", "stake_suggestion": "e.g. $1", "wheel_option": "optional wheel description" }},
    "superfecta":{{ "selection": "#N/#M/#K/#J", "reasoning": "one sentence", "stake_suggestion": "e.g. $0.10" }}
  }},
  "teller_script": {{
    "win":       "Say to teller: '$X to Win on number N, race R'",
    "exacta":    "Say to teller: '$X Exacta, N over M, race R'",
    "trifecta":  "Say to teller: '$X Trifecta, N-M-K, race R'",
    "superfecta":"Say to teller: '$X Superfecta, N-M-K-J, race R'"
  }},
  "overall_summary": "2-3 sentences — technical, for experienced bettors. Complete sentences, do not cut off mid-thought.",
  "overall_summary_beginner": "2-3 sentences — plain English, no jargon, for first-time racegoers. Complete sentences.",
  "beginner_tip": "one concrete action a first-time bettor can take today",
  "confidence": "low/medium/high"
}}"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            temperature=0.2,
            system=SECRETARIAT_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.APIStatusError as exc:
        if exc.status_code == 529:
            raise SecretariatBusyError("Secretariat is busy right now. Try again in 30 seconds.")
        raise

    raw_text = response.content[0].text
    try:
        result = _truncate_analysis(_parse_json(raw_text))
    except json.JSONDecodeError:
        # Retry once with a simplified prompt asking only for JSON
        retry_prompt = (
            "Return ONLY the JSON object from your previous analysis — "
            "no explanation, no markdown, just the raw JSON."
        )
        retry_response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            temperature=0.2,
            system=SECRETARIAT_SYSTEM,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": retry_prompt},
            ]
        )
        result = _truncate_analysis(_parse_json(retry_response.content[0].text))

    try:
        await extract_and_store_fair_prices(race_data.get("race_id", ""), result)
    except Exception:
        pass
    return result


async def stream_analyze_race(race_data: dict, mode: str = "balanced", bankroll: float = None, user_id: int = None, experience_level: str = None):
    """
    Async generator for streaming race analysis.
    Yields ("chunk", str) during generation, then ("result", dict) when done.
    """
    runners = race_data.get("runners", [])
    ts_context = await get_hardware_and_historical_context(runners)
    ts_block = "\n\nADDITIONAL HARDWARE DATA:\n" + "\n\n".join(ts_context.values()) if ts_context else ""

    # Inject rolling calibration data so Secretariat learns from its own history
    cal_context = await get_calibration_context()
    cal_block = f"{cal_context}\n\n---\n\n" if cal_context else ""

    exp_block = _experience_level_block(experience_level)
    prompt = (
        f"RACE ID: {race_data.get('race_id', 'unknown')} | "
        f"MODE: {mode} | "
        "ANALYZE THE FOLLOWING RACE:\n\n"
        f"{cal_block}"
        f"{exp_block}"
        f"""Analyze this race. One sentence per field. Short phrases in arrays.

Race Data:
{json.dumps(_slim_race_for_prompt(race_data), indent=2)}{ts_block}

Mode: {mode} | Bankroll: {f'${bankroll:.2f}' if bankroll else 'unspecified'}

Return this JSON exactly:
{{
  "race_summary": "one sentence",
  "pace_scenario": "one sentence — must state the field size (N runners) and how that shape affects the pace projection",
  "vulnerable_favorite": "horse name or null",
  "runners": [
    {{
      "horse_id": "id",
      "horse_name": "name",
      "number": "program number",
      "contender_score": 0-100,
      "value_score": 0-100,
      "strengths": ["short phrase"],
      "weaknesses": ["short phrase"],
      "summary": "one sentence technical",
      "summary_beginner": "one sentence plain English — no jargon",
      "fair_odds": "e.g. 3/1",
      "recommended_bet": "win/place/show/avoid/use-in-exotics or null"
    }}
  ],
  "predicted_finish": {{
    "first":  {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }},
    "second": {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }},
    "third":  {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }},
    "fourth": {{ "horse_name": "name", "number": "#N", "reasoning": "one sentence" }}
  }},
  "top_contenders": ["#N name1", "#N name2"],
  "longshot_alert": {{
    "horse_name": "name or null",
    "number": "#N or null",
    "reason": "one sentence",
    "odds": "current odds"
  }},
  "recommended_bets": [
    {{
      "bet_type": "Win/Exacta/etc",
      "selection": "#N HorseName",
      "reasoning": "one sentence",
      "suggested_stake": "e.g. $10",
      "risk_level": "low/medium/high"
    }}
  ],
  "bet_recommendations": {{
    "win":       {{ "selection": "#N HorseName", "reasoning": "one sentence", "stake_suggestion": "e.g. $10" }},
    "place":     {{ "selection": "#N HorseName", "reasoning": "one sentence", "stake_suggestion": "e.g. $10" }},
    "show":      {{ "selection": "#N HorseName", "reasoning": "one sentence", "stake_suggestion": "e.g. $10" }},
    "exacta":    {{ "selection": "#N/#M", "reasoning": "one sentence", "stake_suggestion": "e.g. $2", "box_option": "Box #N-#M for $X more" }},
    "trifecta":  {{ "selection": "#N/#M/#K", "reasoning": "one sentence", "stake_suggestion": "e.g. $1", "wheel_option": "optional wheel description" }},
    "superfecta":{{ "selection": "#N/#M/#K/#J", "reasoning": "one sentence", "stake_suggestion": "e.g. $0.10" }}
  }},
  "teller_script": {{
    "win":       "Say to teller: '$X to Win on number N, race R'",
    "exacta":    "Say to teller: '$X Exacta, N over M, race R'",
    "trifecta":  "Say to teller: '$X Trifecta, N-M-K, race R'",
    "superfecta":"Say to teller: '$X Superfecta, N-M-K-J, race R'"
  }},
  "overall_summary": "2-3 sentences — technical, for experienced bettors. Complete sentences, do not cut off mid-thought.",
  "overall_summary_beginner": "2-3 sentences — plain English, no jargon, for first-time racegoers. Complete sentences.",
  "beginner_tip": "one concrete action a first-time bettor can take today",
  "confidence": "low/medium/high"
}}"""
    )

    full_text = ""
    async with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        temperature=0.2,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            full_text += text
            yield ("chunk", text)

    try:
        result = _truncate_analysis(_parse_json(full_text))
    except (json.JSONDecodeError, ValueError, KeyError):
        # JSON was truncated — retry without streaming to get a complete response
        retry_response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            temperature=0.2,
            system=SECRETARIAT_SYSTEM,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": full_text},
                {"role": "user", "content": "Complete the JSON object you started. Return ONLY the complete, valid JSON — no other text."},
            ]
        )
        result = _truncate_analysis(_parse_json(retry_response.content[0].text))

    yield ("result", result)

    # Background: store prediction for accuracy tracking (never blocks stream)
    import asyncio
    import datetime
    predicted_finish = result.get("predicted_finish", {})
    if predicted_finish:
        race_date_raw = race_data.get("date") or race_data.get("race_date")
        try:
            race_date = datetime.date.fromisoformat(str(race_date_raw)) if race_date_raw else datetime.date.today()
        except Exception:
            race_date = datetime.date.today()
        asyncio.create_task(_store_prediction(
            race_id=race_data.get("race_id", ""),
            race_date=race_date,
            track_code=race_data.get("course_id") or race_data.get("track_code") or race_data.get("course", "")[:10],
            race_name=race_data.get("race_name") or race_data.get("title", ""),
            race_type=race_data.get("race_type") or race_data.get("type", ""),
            surface=race_data.get("surface", ""),
            mode=mode,
            predicted_finish=predicted_finish,
            user_id=user_id,
        ))


async def explain_horse(horse_data: dict, race_context: dict = None) -> dict:
    """Explain a single horse's form and prospects in plain English."""
    ts_context = await get_hardware_and_historical_context([horse_data])
    horse_name = horse_data.get("horse") or horse_data.get("horse_name", "")
    ts_block = ""
    if horse_name in ts_context:
        ts_block = "\n\n" + ts_context[horse_name]

    prompt = f"""Assess this horse. Phrases only, no sentences in arrays.

Horse: {json.dumps(_slim_horse_for_explain(horse_data))}
{f"Race: {json.dumps({k: race_context[k] for k in ('course','distance','going','surface','race_class') if k in race_context})}" if race_context else ""}{ts_block}

Return this JSON exactly:
{{
  "verdict": "one sentence — back it or not and why",
  "form_summary": "one sentence on recent form",
  "key_stats": ["short phrase", "short phrase"],
  "strengths": ["short phrase", "short phrase"],
  "concerns": ["short phrase", "short phrase"],
  "good_for_beginners": true
}}"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        temperature=0.2,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    return _truncate_horse(_parse_json(response.content[0].text))


async def recommend_bet_type(
    bankroll: float,
    risk_tolerance: str,
    experience_level: str,
    race_analysis: dict
) -> dict:
    """
    Given a user's profile and race analysis,
    recommend the optimal bet type and stake.
    """
    prompt = f"""A GateSmart user needs a specific bet recommendation.

User Profile:
- Bankroll: ${bankroll:.2f}
- Risk Tolerance: {risk_tolerance}
- Experience Level: {experience_level}

Race Analysis Summary:
{json.dumps(race_analysis, indent=2)}

Return JSON:
{{
  "primary_bet": {{
    "type": "Win/Place/Show/Exacta/etc",
    "selection": "specific horse(s)",
    "stake": dollar_amount_as_number,
    "reasoning": "why this bet for this user's profile",
    "expected_value": "positive/neutral/negative",
    "payout_if_wins": "rough estimate"
  }},
  "alternative_bet": {{
    "type": "...",
    "selection": "...",
    "stake": dollar_amount_as_number,
    "reasoning": "...",
    "payout_if_wins": "..."
  }},
  "bankroll_advice": "Specific advice for this user about managing their bankroll today",
  "bet_sizing_explanation": "Explain to the user why these stake amounts make sense for their bankroll"
}}"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0.2,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    return _parse_json(response.content[0].text)


async def explain_form_string(form_string: str, horse_name: str) -> dict:
    """Decode a raw form string (e.g. '1-3-2-F-1') for a beginner."""
    prompt = f"""Explain this horse racing form string in plain English for a beginner.

Horse: {horse_name}
Form String: {form_string}

CRITICAL READING DIRECTION: UK Racing Post form strings are ALWAYS ordered oldest run FIRST (leftmost character) to most recent run LAST (rightmost character). Read strictly left-to-right when describing the sequence. For example, form "1142" means: oldest run=1st (win), second run=1st (win), third run=4th, most recent run=2nd.

The decoded array must list runs in the same left-to-right order (index 0 = oldest, last index = most recent).

Return JSON:
{{
  "decoded": [
    {{"result": "1", "meaning": "Won", "notes": "brief context"}}
  ],
  "plain_english": "Description reading oldest run first through to most recent",
  "trend": "improving/declining/consistent/mixed",
  "red_flags": ["any worrying patterns"],
  "positive_signs": ["any good patterns"]
}}"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        temperature=0.2,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    return _parse_json(response.content[0].text)


async def score_horse(horse_data: dict, race_context: dict, historical_context: str = "") -> dict:
    """
    Score a single horse across 6 dimensions for the Score Card.
    Returns structured JSON with scores 0-100 per dimension.
    historical_context is the same Equibase/TrackSense block used by the full analysis.
    """
    historical_block = f"\n\nHistorical Data (speed figures, pace ratings, class history):\n{historical_context}" if historical_context else ""
    prompt = f"""Score this horse across exactly 6 handicapping dimensions.

Horse Data:
{json.dumps(horse_data, indent=2)}

Race Context:
{json.dumps(race_context, indent=2)}{historical_block}

Return a JSON object with EXACTLY this structure, no extra fields:
{{
  "horse_id": "from input",
  "horse_name": "from input",
  "scores": {{
    "speed": 0-100,
    "class": 0-100,
    "form": 0-100,
    "pace_fit": 0-100,
    "value": 0-100,
    "trainer_jockey": 0-100
  }},
  "score_notes": {{
    "speed": "one sentence explaining this score",
    "class": "one sentence explaining this score",
    "form": "one sentence explaining this score",
    "pace_fit": "one sentence explaining this score",
    "value": "one sentence explaining this score",
    "trainer_jockey": "one sentence explaining this score"
  }},
  "overall": 0-100,
  "verdict": "one sentence plain English verdict on this horse"
}}

Scoring guide:
- speed: use speed figures and sectional times from historical data if present; otherwise estimate from distance suitability and form
- class: use class history and race conditions from historical data if present; otherwise estimate from level of competition
- form: based on recent finishing positions and trajectory — historical data may show more starts than the form string alone
- pace_fit: based on running style vs expected pace scenario in this race
- value: based on current odds vs estimated true probability (overlay=high score)
- trainer_jockey: use historical trainer/jockey stats if present; otherwise estimate from name recognition and recent form

If historical data is present, your scores MUST reflect it — a horse with strong speed figures should score 70+ on speed.
If historical data is absent for a dimension, score conservatively (40-60) rather than guessing high.
Be honest. A 50 is average. Reserve 80+ for genuinely strong attributes.
A horse can score 90 on speed and 20 on value — that's fine and useful."""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        temperature=0.2,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    return _parse_json(response.content[0].text)


async def score_race(race_data: dict) -> dict:
    """
    Score all horses in a race concurrently. Returns list of score cards.
    Called from the /advisor/scorecard endpoint.
    """
    import asyncio
    from app.core.cache import cache_get, cache_set

    runners = race_data.get("runners", [])
    if not runners:
        return {"race_id": race_data.get("race_id", ""), "scorecards": []}

    race_id = race_data.get("race_id", "")
    cache_key = f"scorecard:{race_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    race_context = {
        "race_id": race_data.get("race_id", ""),
        "course": race_data.get("course", ""),
        "distance": race_data.get("distance", ""),
        "surface": race_data.get("surface", ""),
        "going": race_data.get("going", ""),
        "race_class": race_data.get("race_class", ""),
        "region": race_data.get("region", ""),
        "field_size": len(runners),
        "runners_summary": [
            {
                "horse_id": r.get("horse_id", ""),
                "horse": r.get("horse", ""),
                "odds": r.get("odds", ""),
                "number": r.get("number", "")
            }
            for r in runners
        ]
    }

    # Fetch the same historical context the full analysis uses so scores
    # are grounded in the same Equibase speed figures and TrackSense data.
    historical_context = await get_hardware_and_historical_context(runners)

    async def _score_safe(horse: dict) -> dict:
        horse_name = horse.get("horse") or horse.get("horse_name", "")
        ctx = historical_context.get(horse_name, "")
        try:
            return await score_horse(horse, race_context, historical_context=ctx)
        except Exception as e:
            return {
                "horse_id": horse.get("horse_id", ""),
                "horse_name": horse.get("horse", ""),
                "scores": {
                    "speed": 0, "class": 0, "form": 0,
                    "pace_fit": 0, "value": 0, "trainer_jockey": 0
                },
                "score_notes": {},
                "overall": 0,
                "verdict": "Score unavailable",
                "error": str(e)
            }

    scorecards = await asyncio.gather(*[_score_safe(h) for h in runners])

    result = {
        "race_id": race_data.get("race_id", ""),
        "course": race_data.get("course", ""),
        "scorecards": list(scorecards)
    }
    if race_id:
        await cache_set(cache_key, result, ex=14400)  # 4-hour TTL
    return result


async def debrief_race(
    race_id: str,
    race_data: dict,
    results: dict,
    prior_analysis: dict = None,
) -> dict:
    """Post-race debrief. Explains the result in plain English."""
    prior_block = (
        "Prior Analysis (what Secretariat predicted before the race):\n"
        + json.dumps(prior_analysis, indent=2)
        if prior_analysis
        else "No prior analysis available."
    )

    prompt = f"""You are Secretariat. A race has just finished.
Give a post-race debrief for users who may have bet on this race.

Race: {race_data.get('title', '')} at {race_data.get('course', '')}
Distance: {race_data.get('distance', '')} | Going: {race_data.get('going', '')}

Results:
{json.dumps(results, indent=2)}

{prior_block}

Return a JSON object with EXACTLY this structure:
{{
  "winner": "horse name",
  "winning_odds": "SP if available",
  "headline": "One punchy sentence summarising the result",
  "what_happened": "2-3 sentences explaining the race — pace, who led, how it unfolded",
  "why_winner_won": "2 sentences on what made the winner successful today",
  "prediction_accuracy": "hit/miss/partial — only if prior analysis exists, else null",
  "prediction_notes": "1-2 sentences comparing prediction to result, null if no prior analysis",
  "key_takeaway": "One lesson for bettors from this race result",
  "notable_losers": [
    {{
      "horse": "name",
      "note": "brief explanation of their run"
    }}
  ],
  "beginner_lesson": "Plain English lesson a first-time bettor can learn from this race"
}}"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        temperature=0.2,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    result = _parse_json(response.content[0].text)

    from app.core.cache import cache_set
    await cache_set(f"debrief:{race_id}", result, ex=86400)
    return result


async def extract_and_store_fair_prices(race_id: str, analysis: dict) -> None:
    """
    After a race analysis is generated, extract fair_odds per horse and store
    them in Redis for value alert comparison.
    Key: alerts:fair:{race_id}:{horse_id}
    TTL: 14400 (4 hours)
    """
    from app.core.cache import cache_set
    import datetime
    runners = analysis.get("runners", [])
    for runner in runners:
        horse_id = runner.get("horse_id", "")
        fair_odds = runner.get("fair_odds", "")
        if not horse_id or not fair_odds:
            continue
        try:
            if "/" in str(fair_odds):
                n, d = str(fair_odds).split("/")
                fair_decimal = (int(n) / int(d)) + 1
            else:
                fair_decimal = float(fair_odds)
            key = f"alerts:fair:{race_id}:{horse_id}"
            await cache_set(key, {
                "horse_name": runner.get("horse_name", ""),
                "fair_odds_fractional": fair_odds,
                "fair_decimal": round(fair_decimal, 2),
                "stored_at": datetime.datetime.utcnow().isoformat(),
            }, ex=14400)
        except Exception:
            continue


async def answer_betting_question(question: str, context: dict = None) -> str:
    """Free-form Q&A — Secretariat answers any horse-racing question with substance.

    Uses Anthropic's native web search tool so Secretariat can pull current race
    fields, odds, prep results, and breaking racing news in real time. Falls back
    on its trained knowledge for evergreen topics (history, breeding, strategy,
    handicapping principles).
    """
    import datetime

    today_str = datetime.date.today().strftime("%A, %B %d, %Y")

    prompt = f"""Today is {today_str}.

You are Secretariat answering a question from a GateSmart user. You are an elite handicapper, racing historian, and betting strategist. Engage your full expertise — historical winners, trainer/jockey patterns, breeding, training methodology, pace handicapping, betting strategy, exotics, track biases, racing rules and economics, prep race profiles, anything in the sport.

YOU HAVE WEB SEARCH AND YOU ARE EXPECTED TO USE IT.

You MUST search the web before answering when the question is about ANY of the following:
- Who will win / who's the favorite / who do you like in a specific upcoming race (Derby, Preakness, Belmont, Breeders' Cup, any stakes race, any race "this weekend" / "tomorrow" / "today")
- Who is entered, drawn, scratched, or running in a current race or meet
- Current morning line odds, current betting odds, current points standings
- Recent prep race results, last week's stakes, this season's leaderboards
- Trainer/jockey news, equipment changes, workout reports, breaking racing news
- Anything that depends on the current state of the racing world

When you search, prefer authoritative racing sources: kentuckyderby.com, equibase.com, bloodhorse.com, drf.com (Daily Racing Form), paulickreport.com, thoroughbreddailynews.com, ntra.com, official track sites. Synthesize what you find into a handicapping opinion — don't just paraphrase a webpage.

DO NOT search for evergreen topics already in your training (what a Beyer figure is, what an exacta is, who won the 1973 Belmont, basic handicapping theory). Answer those from knowledge.

REQUIRED OUTPUT FOR "WHO WILL WIN" / RACE-PREDICTION QUESTIONS:
1. Search the current field, current morning line, recent prep results.
2. Open with your TOP PICK named explicitly. Bold it.
3. Give a ranked top 3-4 with a one-sentence reason for each (form, pace fit, post position, trainer pattern, current figure).
4. Optionally: a value angle, a longshot, a horse to fade.
5. Always specific horse names. Never "the favorite" without naming it.

NEVER ACCEPTABLE:
- One-line throwaway answers like "Don't put all your chips on one horse" or "It's hard to say."
- Refusing to pick. The user is asking for your opinion — give one.
- Generic gambling platitudes instead of a real handicap.
- Returning fewer than 4 sentences for a substantive question.
- Answers that don't name specific horses for race-prediction questions.

DEPTH AND TONE:
- Beginner questions (rules, terms, bet types): plain English, concrete example.
- Strategy questions (bankroll, value, exotic structuring): confident, specific, numerical when possible.
- Specific race / horse questions: search first, then deliver a ranked, opinionated read.
- Historical / evergreen: answer from training, with dates and details.

FORMATTING:
- Markdown: **bold** for horse/trainer/jockey names and key terms; numbered or bulleted lists for rankings; ## headings only for multi-section answers.
- Length should fit the question — but for any substantive question, at minimum 4 sentences and a clear, named pick or stance.

Question: {question}
{"Context: " + json.dumps(context) if context else ""}

Reply with the markdown answer directly — no JSON wrapper, no preface, no meta-commentary about your tools."""

    create_args = dict(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        temperature=0.3,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    web_search_tool = [{
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 3,
    }]

    try:
        response = await client.messages.create(**create_args, tools=web_search_tool)
    except anthropic.APIError:
        # If web search is unavailable (SDK mismatch, region, rate limit, billing),
        # still answer the question from training.
        response = await client.messages.create(**create_args)

    answer = _extract_text(response)

    # Defensive retry: if the model returned a one-liner non-answer to a
    # substantive question, force it to use the search tool and try again.
    if _is_throwaway(answer) and _looks_substantive(question):
        try:
            response = await client.messages.create(
                **create_args,
                tools=web_search_tool,
                tool_choice={"type": "tool", "name": "web_search"},
            )
            answer = _extract_text(response) or answer
        except anthropic.APIError:
            pass

    return answer


def _extract_text(response) -> str:
    """Pull all text blocks out of a messages response and join them.

    Web search interleaves server_tool_use / web_search_tool_result blocks
    between text blocks. Joining all text blocks captures both the model's
    reasoning narration and the final synthesized answer, so we never lose
    content to a too-narrow "last block only" rule.
    """
    parts = [
        getattr(b, "text", "").strip()
        for b in response.content
        if getattr(b, "type", None) == "text" and getattr(b, "text", "")
    ]
    return "\n\n".join(p for p in parts if p).strip()


def _is_throwaway(answer: str) -> bool:
    """Heuristic: did the model bail out with a non-answer?"""
    a = (answer or "").strip()
    return len(a) < 80 or a.lower().startswith(("don't put", "it's hard", "i can't", "i cannot"))


def _looks_substantive(question: str) -> bool:
    """Heuristic: does the question deserve a real handicap, not a one-liner?"""
    q = (question or "").lower()
    triggers = (
        "who will", "who do you", "who's going to", "who is going to",
        "who's the favorite", "what's the favorite", "best bet",
        "your pick", "your top pick", "win the", "this weekend",
        "tomorrow", "today", "current odds", "morning line",
    )
    return any(t in q for t in triggers)


# ── Prediction Storage ────────────────────────────────────────────────────────

async def _store_prediction(
    race_id: str,
    race_date,
    track_code: str,
    race_name: str,
    race_type: str,
    surface: str,
    mode: str,
    predicted_finish: dict,
    user_id: int = None,
) -> None:
    """
    Silently insert a RacePrediction row after analysis completes.
    Uses INSERT ... ON CONFLICT DO NOTHING — safe to call multiple times.
    Never raises; all exceptions are suppressed.
    """
    try:
        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import RacePrediction
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        if not _AsyncSessionLocal:
            return

        first = predicted_finish.get("first") or {}
        second = predicted_finish.get("second") or {}
        third = predicted_finish.get("third") or {}
        fourth = predicted_finish.get("fourth") or {}

        row = {
            "race_id": race_id,
            "race_date": race_date,
            "track_code": track_code,
            "race_name": race_name,
            "race_type": race_type,
            "surface": surface,
            "analysis_mode": mode,
            "user_id": user_id,
            "predicted_first": first.get("horse_name"),
            "predicted_second": second.get("horse_name"),
            "predicted_third": third.get("horse_name"),
            "predicted_fourth": fourth.get("horse_name"),
            "predicted_first_num": first.get("number"),
        }

        constraint = "uq_prediction_race_mode_user" if user_id is not None else "uq_race_prediction"
        async with _AsyncSessionLocal() as db:
            stmt = pg_insert(RacePrediction).values(**row)
            stmt = stmt.on_conflict_do_nothing(constraint=constraint)
            await db.execute(stmt)
            await db.commit()
    except Exception:
        pass  # Silent — never block the stream path


# ── Daily Email Report ────────────────────────────────────────────────────────

async def _compute_category_trends(report_date, lookback_days: int = 7) -> dict:
    """
    Cross-day trend analysis grounded in real settled results.

    Groups the last `lookback_days` of NA predictions by (track_code, race_type)
    and surfaces three buckets so the digest's "How I'm Evolving" section is
    anchored in movement, not single-day narrative:
      - persistent_weak: category trailing the 7-day baseline by ≥10pts, n≥5
      - regressing:      today worse than prior-6-days by ≥15pts, today n≥2
      - improving:       today better than prior-6-days by ≥15pts, today n≥2

    Returns { "block": str, "persistent_weak": [...], "regressing": [...], "improving": [...] }.
    `block` is a formatted string ready for prompt injection and email display.
    Empty block when sample is insufficient.
    """
    import datetime
    from collections import defaultdict

    if report_date is None:
        return {"block": "", "persistent_weak": [], "regressing": [], "improving": []}

    start_date = report_date - datetime.timedelta(days=lookback_days - 1)

    try:
        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import RacePrediction
        from sqlalchemy import select, and_, or_

        if not _AsyncSessionLocal:
            return {"block": "", "persistent_weak": [], "regressing": [], "improving": []}

        async with _AsyncSessionLocal() as db:
            result = await db.execute(
                select(RacePrediction).where(
                    and_(
                        RacePrediction.race_date >= start_date,
                        RacePrediction.race_date <= report_date,
                        RacePrediction.result_fetched == True,  # noqa: E712
                        or_(RacePrediction.region == "na", RacePrediction.region == None),  # noqa: E711
                    )
                )
            )
            rows = result.scalars().all()
    except Exception:
        return {"block": "", "persistent_weak": [], "regressing": [], "improving": []}

    if not rows or len(rows) < 15:
        return {"block": "", "persistent_weak": [], "regressing": [], "improving": []}

    # Group by (track, race_type) — the dimension where failures concentrate
    buckets: dict = defaultdict(lambda: {"window_n": 0, "window_w": 0, "today_n": 0, "today_w": 0})
    track_buckets: dict = defaultdict(lambda: {"window_n": 0, "window_w": 0, "today_n": 0, "today_w": 0})
    window_total = {"n": 0, "w": 0}
    for r in rows:
        track = r.track_code or "?"
        rtype = r.race_type or "?"
        key = (track, rtype)
        is_today = r.race_date == report_date
        hit = 1 if r.top_pick_correct else 0
        buckets[key]["window_n"] += 1
        buckets[key]["window_w"] += hit
        track_buckets[track]["window_n"] += 1
        track_buckets[track]["window_w"] += hit
        window_total["n"] += 1
        window_total["w"] += hit
        if is_today:
            buckets[key]["today_n"] += 1
            buckets[key]["today_w"] += hit
            track_buckets[track]["today_n"] += 1
            track_buckets[track]["today_w"] += hit

    if window_total["n"] == 0:
        return {"block": "", "persistent_weak": [], "regressing": [], "improving": []}

    baseline = window_total["w"] / window_total["n"]

    persistent_weak: list[dict] = []
    regressing: list[dict] = []
    improving: list[dict] = []

    def _classify(entry: dict, b: dict) -> None:
        wr = entry["window_rate"]
        today_rate = entry["today_rate"]
        prior_rate = entry["prior_rate"]
        if b["window_n"] >= 5 and wr <= baseline - 0.10:
            persistent_weak.append(entry)
        if b["today_n"] >= 2 and entry["prior_n"] >= 3 and today_rate is not None and prior_rate is not None:
            if today_rate <= prior_rate - 0.15:
                regressing.append(entry)
            elif today_rate >= prior_rate + 0.15:
                improving.append(entry)

    def _make_entry(track: str, rtype: str, b: dict) -> dict:
        prior_n = b["window_n"] - b["today_n"]
        prior_w = b["window_w"] - b["today_w"]
        return {
            "track": track,
            "race_type": rtype,
            "window_rate": b["window_w"] / b["window_n"],
            "window_n": b["window_n"],
            "window_w": b["window_w"],
            "today_rate": (b["today_w"] / b["today_n"]) if b["today_n"] else None,
            "today_n": b["today_n"],
            "today_w": b["today_w"],
            "prior_rate": (prior_w / prior_n) if prior_n else None,
            "prior_n": prior_n,
        }

    # Per-(track, type) buckets — skip "?" types since they're a data-completeness artifact
    for (track, rtype), b in buckets.items():
        if rtype == "?" or b["window_n"] < 4:
            continue
        _classify(_make_entry(track, rtype, b), b)

    # Track-overall buckets — surface track-wide signal even when no single race-type bucket clears the floor
    for track, b in track_buckets.items():
        if track == "?" or b["window_n"] < 5:
            continue
        _classify(_make_entry(track, "all types", b), b)

    # Dedupe: when (track, "all types") qualifies, suppress that track's per-type entries in the same bucket
    def _dedupe(entries: list) -> list:
        tracks_with_all = {e["track"] for e in entries if e["race_type"] == "all types"}
        return [e for e in entries if e["race_type"] == "all types" or e["track"] not in tracks_with_all]

    persistent_weak = _dedupe(persistent_weak)
    regressing = _dedupe(regressing)
    improving = _dedupe(improving)

    persistent_weak.sort(key=lambda e: (e["window_rate"], -e["window_n"]))
    regressing.sort(key=lambda e: (e["today_rate"] - e["prior_rate"]))
    improving.sort(key=lambda e: -(e["today_rate"] - e["prior_rate"]))

    persistent_weak = persistent_weak[:3]
    regressing = regressing[:3]
    improving = improving[:3]

    if not (persistent_weak or regressing or improving):
        return {"block": "", "persistent_weak": [], "regressing": [], "improving": []}

    def _fmt(e: dict) -> str:
        parts = [f"{e['track']} {e['race_type']}: {lookback_days}d {e['window_w']}/{e['window_n']} ({e['window_rate']:.0%})"]
        if e["today_n"]:
            parts.append(f"today {e['today_w']}/{e['today_n']}")
        return " — ".join(parts)

    lines: list[str] = [
        f"{lookback_days}-DAY CATEGORY TRENDS (baseline {baseline:.0%} on {window_total['n']} races):"
    ]
    if persistent_weak:
        lines.append("Persistent weak spots (below baseline across the window):")
        lines.extend(f"  - {_fmt(e)}" for e in persistent_weak)
    if regressing:
        lines.append("Regressing today vs prior 6 days:")
        lines.extend(f"  - {_fmt(e)}" for e in regressing)
    if improving:
        lines.append("Improving today vs prior 6 days:")
        lines.extend(f"  - {_fmt(e)}" for e in improving)

    return {
        "block": "\n".join(lines),
        "persistent_weak": persistent_weak,
        "regressing": regressing,
        "improving": improving,
    }


def _render_trends_html(trends: dict) -> str:
    """Render the 7-day trend buckets as an HTML section for the digest email."""
    if not trends or not trends.get("block"):
        return ""

    def _row(e: dict) -> str:
        today_cell = (
            f"{e['today_w']}/{e['today_n']} ({e['today_rate']:.0%})"
            if e.get("today_n") else "—"
        )
        return (
            '<tr>'
            f'<td style="padding:3px 8px">{e["track"]}</td>'
            f'<td style="padding:3px 8px">{e["race_type"]}</td>'
            f'<td style="padding:3px 8px">{e["window_w"]}/{e["window_n"]} ({e["window_rate"]:.0%})</td>'
            f'<td style="padding:3px 8px">{today_cell}</td>'
            '</tr>'
        )

    def _section(title: str, entries: list, color: str) -> str:
        if not entries:
            return ""
        rows = "\n".join(_row(e) for e in entries)
        return (
            f'<h4 style="color:{color};margin:12px 0 4px">{title}</h4>'
            '<table style="border-collapse:collapse;width:100%;font-size:12px">'
            '<tr style="background:#eee"><th style="padding:3px 8px;text-align:left">Track</th>'
            '<th style="padding:3px 8px;text-align:left">Type</th>'
            '<th style="padding:3px 8px;text-align:left">7-day</th>'
            '<th style="padding:3px 8px;text-align:left">Today</th></tr>'
            f'{rows}</table>'
        )

    sections = "".join([
        _section("Persistent weak spots", trends.get("persistent_weak", []), "#a33"),
        _section("Regressing today", trends.get("regressing", []), "#c06"),
        _section("Improving today", trends.get("improving", []), "#2d6a2d"),
    ])
    if not sections:
        return ""
    return (
        '<h2 style="color:#555">📊 7-Day Category Trends</h2>'
        + sections
    )


# ── Morning Line Email ────────────────────────────────────────────────────────


def _format_post_time(post_et: str) -> str:
    """Convert stored 24-hour ET ("HH:MM") into a printable
    "1:05 PM ET / 12:05 PM CT" string. Returns "—" when missing or malformed."""
    if not post_et or len(post_et) < 4:
        return "—"
    try:
        h, m = post_et.split(":")
        h_et = int(h) % 24
        m_int = int(m)
    except ValueError:
        return post_et

    def _twelve(h24: int) -> str:
        suffix = "AM" if h24 < 12 else "PM"
        h12 = h24 % 12 or 12
        return f"{h12}:{m_int:02d} {suffix}"

    h_ct = (h_et - 1) % 24
    return f"{_twelve(h_et)} ET / {_twelve(h_ct)} CT"


async def generate_morning_line_email(predictions: list, report_date) -> dict:
    """Builds Secretariat's pre-race "Morning Line" email.

    For every NA race today, surfaces the Win / Place / Show picks. No LLM
    call — picks were already written by nightly_predict_all.py earlier in
    the morning. Layout is print-friendly: per-track bordered tables with
    visible dividers between sections.

    Returns { "subject": str, "html": str, "text": str }.
    """
    import datetime
    from itertools import groupby

    today_str = (
        report_date.strftime("%A, %B %d, %Y") if report_date else str(datetime.date.today())
    )
    short_date = report_date.strftime("%a %b %-d") if report_date else ""

    predictions = sorted(
        predictions,
        key=lambda p: (
            p.track_code or "ZZZ",
            getattr(p, "post_time_et", None) or "99:99",
            p.race_name or "",
        ),
    )

    track_groups = [(t, list(items)) for t, items in groupby(predictions, key=lambda p: p.track_code or "?")]
    total_picks = len(predictions)
    total_tracks = len(track_groups)

    # Cell border style reused throughout the print-friendly layout
    cell = "padding:6px 8px;border:1px solid #888"
    header_cell = "padding:8px;border:1px solid #222;background:#222;color:#fff;text-align:left"
    track_banner = (
        "padding:10px 12px;background:#c8a84b;color:#1a1a1a;"
        "font-weight:bold;font-size:15px;border:2px solid #1a1a1a;"
        "border-bottom:none;letter-spacing:0.3px"
    )

    text_chunks: list[str] = []
    html_track_blocks: list[str] = []

    for track, items in track_groups:
        track_full = TRACK_NAMES.get((track or "").upper(), track)
        header = f"{track} — {track_full}" if track_full and track_full != track else track

        text_chunks.append("")
        text_chunks.append("=" * 70)
        text_chunks.append(f"  {header}  ({len(items)} races)")
        text_chunks.append("=" * 70)

        rows_html: list[str] = []
        for p in items:
            num = (p.predicted_first_num or "").lstrip("#").strip()
            win_label = f"#{num} {p.predicted_first}" if num else (p.predicted_first or "?")
            place_label = p.predicted_second or "—"
            show_label = p.predicted_third or "—"
            post = _format_post_time(p.post_time_et or "")
            type_label = p.race_type or p.surface or "—"
            race_label = p.race_name or p.race_id or ""

            text_chunks.append(
                f"  {post} | {race_label} | {type_label}\n"
                f"      W: {win_label}\n"
                f"      P: {place_label}\n"
                f"      S: {show_label}"
            )

            rows_html.append(
                f'<tr>'
                f'<td style="{cell};white-space:nowrap;font-variant-numeric:tabular-nums">{post}</td>'
                f'<td style="{cell}">{race_label}</td>'
                f'<td style="{cell};color:#444;font-size:12px">{type_label}</td>'
                f'<td style="{cell}"><strong>{win_label}</strong></td>'
                f'<td style="{cell}">{place_label}</td>'
                f'<td style="{cell}">{show_label}</td>'
                f'</tr>'
            )

        html_track_blocks.append(
            f'<div style="margin:24px 0;page-break-inside:avoid">'
            f'  <div style="{track_banner}">{header} &nbsp;·&nbsp; {len(items)} races</div>'
            f'  <table style="border-collapse:collapse;width:100%;font-size:13px;'
            f'border:2px solid #1a1a1a;border-top:none">'
            f'    <tr>'
            f'      <th style="{header_cell}">Post Time</th>'
            f'      <th style="{header_cell}">Race</th>'
            f'      <th style="{header_cell}">Type</th>'
            f'      <th style="{header_cell}">Win</th>'
            f'      <th style="{header_cell}">Place</th>'
            f'      <th style="{header_cell}">Show</th>'
            f'    </tr>'
            f'    {"".join(rows_html)}'
            f'  </table>'
            f'</div>'
        )

    subject = (
        f"🏇 Secretariat's Morning Line — {short_date} | "
        f"{total_picks} picks across {total_tracks} tracks"
    )

    legend_text = (
        "W = Win pick · P = Place pick (2nd-most-likely) · S = Show pick (3rd-most-likely)\n"
        "All post times shown in Eastern / Central."
    )

    text_body = (
        f"SECRETARIAT'S MORNING LINE — {today_str.upper()}\n"
        f"{'='*70}\n\n"
        f"  {total_picks} picks across {total_tracks} tracks\n"
        f"\n{legend_text}\n"
        + "\n".join(text_chunks)
        + "\n"
    )

    html_body = f"""<div style="font-family:Georgia,serif;max-width:900px;margin:auto;color:#1a1a1a;padding:8px">
  <h1 style="border-bottom:3px solid #c8a84b;padding-bottom:8px;margin-bottom:4px">
    🐎 Secretariat's Morning Line
  </h1>
  <p style="color:#666;font-size:13px;margin-top:0">{today_str}</p>

  <table style="width:100%;border:2px solid #c8a84b;border-collapse:collapse;margin:16px 0">
    <tr style="background:#f8f4ec">
      <td style="padding:14px;text-align:center;border-right:1px solid #c8a84b">
        <div style="font-size:26px;font-weight:bold">{total_picks}</div>
        <div style="font-size:11px;color:#666">Picks</div>
      </td>
      <td style="padding:14px;text-align:center">
        <div style="font-size:26px;font-weight:bold">{total_tracks}</div>
        <div style="font-size:11px;color:#666">Tracks</div>
      </td>
    </tr>
  </table>

  <p style="background:#f8f4ec;padding:10px 14px;border:1px solid #c8a84b;font-size:12px;color:#444;line-height:1.5;margin:16px 0">
    <strong>W</strong> = Win pick &nbsp;·&nbsp; <strong>P</strong> = Place pick (2nd-most-likely) &nbsp;·&nbsp;
    <strong>S</strong> = Show pick (3rd-most-likely)<br>
    All post times shown in Eastern / Central.
  </p>

  {"".join(html_track_blocks)}

  <p style="font-size:11px;color:#999;margin-top:24px;border-top:1px solid #ccc;padding-top:8px">
    Secretariat · GateSmart · {today_str} · pre-race picks generated at 11 AM ET
  </p>
</div>"""

    return {"subject": subject, "html": html_body, "text": text_body}


async def generate_daily_email_report(report, predictions: list) -> dict:
    """
    Builds a complete daily digest email for every settled race.

    Strategy: Python builds the full results table (guaranteed complete coverage,
    zero token cost). Claude writes only the pattern analysis sections.
    Returns { "subject": str, "html": str, "text": str }
    """
    import datetime
    from collections import defaultdict

    today_str = report.report_date.strftime("%A, %B %d, %Y") if report.report_date else str(datetime.date.today())

    hits = [p for p in predictions if p.top_pick_correct]
    misses = [p for p in predictions if not p.top_pick_correct]
    total = len(predictions)
    win_pct = f"{len(hits)/total:.1%}" if total else "0.0%"
    itm_list = [p for p in predictions if p.in_the_money]
    itm_pct = f"{len(itm_list)/total:.1%}" if total else "0.0%"
    place_hits = [p for p in predictions if getattr(p, "place_pick_correct", False)]
    show_hits = [p for p in predictions if getattr(p, "show_pick_correct", False)]
    place_pct = f"{len(place_hits)/total:.1%}" if total else "0.0%"
    show_pct = f"{len(show_hits)/total:.1%}" if total else "0.0%"

    # ── Build complete results table in Python (every race, no LLM needed) ──
    def _row_text(p):
        icon = "✅" if p.top_pick_correct else ("🔶" if p.in_the_money else "❌")
        return (
            f"{icon} {p.race_name or p.race_id} | {p.track_code or '?'} | "
            f"{p.race_type or getattr(p, 'surface', None) or '?'} | Picked: {p.predicted_first or '?'} | "
            f"Won: {p.actual_first or 'N/A'}"
        )

    def _row_html(p):
        icon = "✅" if p.top_pick_correct else ("🔶" if p.in_the_money else "❌")
        bg = "#f0fff0" if p.top_pick_correct else ("#fffbe6" if p.in_the_money else "#fff5f5")
        return (
            f'<tr style="background:{bg}">'
            f'<td style="padding:4px 8px">{icon}</td>'
            f'<td style="padding:4px 8px">{p.race_name or p.race_id}</td>'
            f'<td style="padding:4px 8px">{p.track_code or "?"}</td>'
            f'<td style="padding:4px 8px">{p.race_type or getattr(p, "surface", None) or "?"}</td>'
            f'<td style="padding:4px 8px"><strong>{p.predicted_first or "?"}</strong></td>'
            f'<td style="padding:4px 8px">{p.actual_first or "N/A"}</td>'
            f'</tr>'
        )

    # Group by track, then race order within each track, so the digest reads track-by-track
    from itertools import groupby

    predictions = sorted(
        predictions,
        key=lambda p: (
            p.track_code or "ZZZ",
            getattr(p, "post_time_et", None) or "99:99",
            p.race_name or "",
        ),
    )

    track_groups = [(track, list(items)) for track, items in groupby(predictions, key=lambda p: p.track_code or "?")]

    text_chunks: list[str] = []
    html_chunks: list[str] = []
    for idx, (track, items) in enumerate(track_groups):
        track_wins = sum(1 for p in items if p.top_pick_correct)
        header = f"{track} — {track_wins}/{len(items)}"
        if text_chunks:
            text_chunks.append("")  # blank line between track sections
        text_chunks.append(f"── {header} ──")
        text_chunks.extend(_row_text(p) for p in items)

        if idx > 0:
            html_chunks.append(
                '<tr><td colspan="6" style="padding:0;height:12px;background:#fff"></td></tr>'
            )
        html_chunks.append(
            f'<tr style="background:#c8a84b;color:#1a1a1a">'
            f'<td colspan="6" style="padding:8px;font-weight:bold;font-size:14px">{header}</td>'
            f'</tr>'
        )
        html_chunks.extend(_row_html(p) for p in items)

    text_table = "\n".join(text_chunks)
    html_rows = "\n".join(html_chunks)
    html_table = (
        '<table style="border-collapse:collapse;width:100%;font-size:13px">'
        '<tr style="background:#222;color:#fff">'
        '<th style="padding:6px 8px"></th>'
        '<th style="padding:6px 8px;text-align:left">Race</th>'
        '<th style="padding:6px 8px;text-align:left">Track</th>'
        '<th style="padding:6px 8px;text-align:left">Type</th>'
        '<th style="padding:6px 8px;text-align:left">My Pick</th>'
        '<th style="padding:6px 8px;text-align:left">Winner</th>'
        '</tr>'
        + html_rows
        + '</table>'
    )

    # ── Aggregate patterns for Claude's analysis (compact, not raw rows) ──
    by_track: dict = defaultdict(lambda: {"wins": 0, "total": 0})
    by_type: dict = defaultdict(lambda: {"wins": 0, "total": 0})
    by_surface: dict = defaultdict(lambda: {"wins": 0, "total": 0})
    for p in predictions:
        for bucket, key in [
            (by_track, p.track_code or "?"),
            (by_type, p.race_type or getattr(p, "surface", None) or "?"),
            (by_surface, getattr(p, "surface", None) or "?"),
        ]:
            bucket[key]["total"] += 1
            if p.top_pick_correct:
                bucket[key]["wins"] += 1

    def _fmt_bucket(b):
        return ", ".join(
            f"{k}: {v['wins']}/{v['total']}"
            for k, v in sorted(b.items(), key=lambda x: -x[1]["total"])
        )

    hit_sample = "; ".join(
        f"{p.predicted_first} won at {p.track_code or '?'} ({p.race_type or getattr(p, 'surface', None) or '?'})"
        for p in hits[:15]
    ) or "none"
    miss_sample = "; ".join(
        f"picked {p.predicted_first}, {p.actual_first or 'N/A'} won at {p.track_code or '?'} ({p.race_type or getattr(p, 'surface', None) or '?'})"
        for p in misses[:20]
    ) or "none"

    # Track-code reference for today's tracks — prevents the model from hallucinating
    # full names from codes (e.g. FP → "Finger Lakes Park"). Only includes codes
    # that actually appeared in today's races and have a known mapping.
    todays_codes = sorted({(p.track_code or "").upper() for p in predictions if p.track_code})
    track_ref_lines = [f"  {c} = {TRACK_NAMES[c]}" for c in todays_codes if c in TRACK_NAMES]
    track_ref_block = (
        "TRACK CODE REFERENCE (use these full names if you mention a track by name):\n"
        + "\n".join(track_ref_lines)
        + "\n"
    ) if track_ref_lines else ""

    # Cross-day trends — grounds "How I'm Evolving" in actual category movement
    trends = await _compute_category_trends(report.report_date, lookback_days=7)
    trends_block = trends.get("block", "")

    # Load stored lessons so the email reflects what's actually being applied
    stored_lessons_block = ""
    try:
        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import SecretariatCalibration
        if _AsyncSessionLocal:
            async with _AsyncSessionLocal() as db:
                cal = await db.get(SecretariatCalibration, 1)
            if cal and cal.lessons:
                stored_lessons_block = (
                    "\nLESSONS CURRENTLY IN MY MEMORY (applied to every analysis):\n"
                    + "\n".join(f"  - {l}" for l in cal.lessons[:8])
                    + "\n"
                )
    except Exception:
        pass

    analysis_prompt = f"""Date: {today_str}
Total races: {total}
Win pick (1st): {len(hits)} ({win_pct}) | Win pick ITM (1st-3rd): {report.in_the_money} ({itm_pct})
Place pick (2nd choice finished top 2): {len(place_hits)} ({place_pct})
Show pick (3rd choice finished top 3): {len(show_hits)} ({show_pct})

By track (win-pick wins/total): {_fmt_bucket(by_track)}
By race type (win-pick wins/total): {_fmt_bucket(by_type)}
By surface (win-pick wins/total): {_fmt_bucket(by_surface)}

Sample correct picks: {hit_sample}
Sample misses: {miss_sample}
{track_ref_block}{(trends_block + chr(10)) if trends_block else ""}{stored_lessons_block}
Write three analysis sections for Secretariat's nightly digest. Be specific and honest.
Treat the win, place, and show pick rates as three separate accuracy signals — a strong show
rate with a weak win rate means the model is identifying live contenders but mis-ranking them at
the top, which is a different problem than missing the contenders entirely.
When you reference a track, use ONLY the code (e.g. "FL", "FP", "CD") OR the exact full name from
the TRACK CODE REFERENCE above. NEVER invent or guess a full track name from a code — different
codes can look similar (FP is Fonner Park, FL is Finger Lakes; do not confuse them).
When the trend data above shows persistent weak spots or regressions, you MUST name them and
treat single-day improvements as provisional until they repeat. In "how_im_evolving", only
claim a prior lesson is working if a category it targeted has actually improved in the trend data.
Return JSON exactly:
{{
  "subject": "Secretariat – {today_str} | {len(hits)}/{total} ({win_pct}) win rate",
  "what_went_right": "2-4 sentences: which patterns produced correct picks today and why those signals worked. If place or show rates are strong, name what's working at the contender-identification level even when the top pick missed. Name specific tracks, race types, or surfaces if there's a pattern.",
  "what_went_wrong": "2-4 sentences: which patterns failed and the likely reason. Distinguish missing-the-contenders failures (low show rate) from mis-ranking failures (decent show rate, weak win rate). Be honest about systematic weaknesses, not just bad luck.",
  "how_im_evolving": "2-4 sentences: specific adjustments I will make, grounded in the 7-day trend data above. If a persistent weak spot exists, name it and commit to a concrete gate. If a prior lesson has NOT moved its target category in the trend data, say so plainly."
}}"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        temperature=0.4,
        system=(
            "You are Secretariat, an AI horse racing handicapper reviewing your daily performance. "
            "Write in first person. Be analytical, honest, and specific — name tracks, race types, and patterns. "
            "Do not use filler phrases. Every sentence must contain a concrete observation."
        ),
        messages=[{"role": "user", "content": analysis_prompt}],
    )

    analysis = _parse_json(response.content[0].text)

    subject = analysis.get("subject", f"Secretariat – {today_str} | {len(hits)}/{total} wins")
    what_right = analysis.get("what_went_right", "")
    what_wrong = analysis.get("what_went_wrong", "")
    evolving = analysis.get("how_im_evolving", "")

    # ── Assemble final email in Python ──
    trends_text_section = f"\n7-DAY TRENDS\n{trends_block}\n" if trends_block else ""

    text_body = f"""SECRETARIAT DAILY DIGEST — {today_str.upper()}
{'='*60}

SCORECARD
  Races analyzed : {total}
  Win pick (1st) : {len(hits)} ({win_pct})
  Win pick ITM   : {report.in_the_money} ({itm_pct})
  Place pick     : {len(place_hits)} ({place_pct})
  Show pick      : {len(show_hits)} ({show_pct})

WHAT WENT RIGHT
{what_right}

WHAT WENT WRONG
{what_wrong}

HOW I'M EVOLVING
{evolving}
{trends_text_section}
COMPLETE RESULTS ({total} races)
{'─'*60}
{text_table}
"""

    html_body = f"""<div style="font-family:Georgia,serif;max-width:800px;margin:auto;color:#1a1a1a">
  <h1 style="border-bottom:3px solid #c8a84b;padding-bottom:8px">
    🏇 Secretariat Daily Digest
  </h1>
  <p style="color:#666;font-size:13px">{today_str}</p>

  <table style="width:100%;background:#f8f4ec;border-radius:6px;padding:16px;margin:16px 0">
    <tr>
      <td style="font-size:24px;font-weight:bold;text-align:center">{len(hits)}/{total}</td>
      <td style="font-size:24px;font-weight:bold;text-align:center">{win_pct}</td>
      <td style="font-size:24px;font-weight:bold;text-align:center">{itm_pct}</td>
      <td style="font-size:24px;font-weight:bold;text-align:center">{place_pct}</td>
      <td style="font-size:24px;font-weight:bold;text-align:center">{show_pct}</td>
    </tr>
    <tr>
      <td style="text-align:center;color:#666;font-size:11px">Wins / Races</td>
      <td style="text-align:center;color:#666;font-size:11px">Win Rate</td>
      <td style="text-align:center;color:#666;font-size:11px">Win Pick ITM</td>
      <td style="text-align:center;color:#666;font-size:11px">Place Pick</td>
      <td style="text-align:center;color:#666;font-size:11px">Show Pick</td>
    </tr>
  </table>

  <h2 style="color:#2d6a2d">✅ What Went Right</h2>
  <p>{what_right}</p>

  <h2 style="color:#a33">❌ What Went Wrong</h2>
  <p>{what_wrong}</p>

  <h2 style="color:#c8a84b">🔄 How I'm Evolving</h2>
  <p>{evolving}</p>
{_render_trends_html(trends)}
  <h2>📋 Complete Results — All {total} Races</h2>
  {html_table}

  <p style="font-size:11px;color:#999;margin-top:24px">
    Secretariat · GateSmart · {today_str}
  </p>
</div>"""

    return {"subject": subject, "html": html_body, "text": text_body}


# ── Calibration Context ───────────────────────────────────────────────────────

async def get_calibration_context() -> str:
    """
    Returns a context string injected into every analysis prompt.
    Returns empty string if < 20 samples or calibration row missing.
    """
    try:
        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import SecretariatCalibration

        if not _AsyncSessionLocal:
            return ""

        async with _AsyncSessionLocal() as db:
            cal = await db.get(SecretariatCalibration, 1)

        if not cal or cal.sample_size < 20:
            return ""

        lines = [
            f"YOUR RECENT PERFORMANCE ({cal.sample_size} races, 30-day rolling):",
            f"Overall win rate: {cal.rolling_win_rate:.0%}",
        ]

        if cal.weak_spots:
            lines.append("AREAS TO BE MORE CAUTIOUS:")
            for spot in cal.weak_spots[:3]:
                lines.append(f"  - {spot}")

        if cal.strong_spots:
            lines.append("YOUR STRENGTHS (be more decisive):")
            for spot in cal.strong_spots[:3]:
                lines.append(f"  - {spot}")

        if cal.lessons:
            lines.append("LESSONS FROM RECENT RACES (apply these now):")
            for lesson in cal.lessons[:5]:
                lines.append(f"  - {lesson}")

        lines.append(
            "Use this to calibrate confidence. "
            "Widen contenders in weak areas. Be decisive in strong areas. "
            "Apply the lessons above — they come from your own mistakes and wins."
        )
        return "\n".join(lines)
    except Exception:
        return ""
