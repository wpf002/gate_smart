"""
Secretariat — GateSmart's AI handicapping engine.
Powered by Claude (Anthropic). This is the core intelligence of the platform.
All race analysis, horse evaluation, and betting recommendations flow through here.
"""
import anthropic
import json
from app.core.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


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


SECRETARIAT_SYSTEM = """You are Secretariat, an elite horse racing handicapper and betting strategist. Your primary expertise is North American thoroughbred racing — US tracks, US trainers, US jockeys, and US betting markets. You also have strong working knowledge of UK, Irish, and international racing.

Your job inside GateSmart is to analyze races and give users clear, honest, actionable betting intelligence.

US RACING EXPERTISE (primary focus):
- Beyer Speed Figures — the gold standard for US handicapping. Always reference Beyers when available.
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

BEGINNER EDUCATION:
- Always explain US-specific terms when they appear (Beyer, claiming race, allowance, etc.)
- Explain bet types in plain English with examples

Your tone: direct, confident. Sharp handicapper, no padding.

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
    from app.core.cache import cache_get

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

            # ── Equibase historical speed figures ─────────────────────────────
            eq_key = re.sub(r"[^a-z0-9_]", "", horse_name.lower().replace(" ", "_"))
            try:
                equibase_data = await cache_get(f"equibase:horse:{eq_key}")
                if equibase_data and isinstance(equibase_data, list) and len(equibase_data) > 0:
                    ratings = [r["speed_rating"] for r in equibase_data if r.get("speed_rating") is not None]
                    if ratings:
                        best_rating = max(ratings)
                        avg_rating = round(sum(ratings) / len(ratings), 1)
                        recent_rating = equibase_data[0].get("speed_rating")
                        n_races_eq = len(equibase_data)

                        best_race = max(
                            (r for r in equibase_data if r.get("speed_rating") is not None),
                            key=lambda x: x["speed_rating"],
                        )

                        equibase_ctx = (
                            f"EQUIBASE HISTORICAL DATA (2023 US result charts):\n"
                            f"{horse_name} — {n_races_eq} races in dataset:\n"
                            f"- Best speed rating: {best_rating} (Equibase/TrackMaster figure, Beyer-comparable scale)\n"
                            f"- Recent speed rating: {recent_rating} (most recent 2023 race)\n"
                            f"- Average speed rating: {avg_rating}\n"
                            f"- Best performance: {best_race['race_type']} at {best_race['track_name']}, "
                            f"{best_race['race_date']}, finished {best_race['official_finish']}, "
                            f"rating {best_race['speed_rating']}\n"
                            f"Note: Figures are on the Beyer Speed Figure scale (0-130+). "
                            f"100+ = graded stakes quality. 85-99 = allowance/stakes competitive. "
                            f"70-84 = mid-level claiming. Below 70 = bottom claiming."
                        )
            except Exception:
                pass

            # ── Equibase past performances ────────────────────────────────────
            pp_ctx = None
            try:
                pp_data = await cache_get(f"equibase:pp:{eq_key}")
                if pp_data and isinstance(pp_data, list) and len(pp_data) > 0:
                    recent = pp_data[:10]  # up to 10 most recent starts
                    sf_list = [r["speed_figure"] for r in recent if r.get("speed_figure") is not None]
                    pace_lines = []
                    for r in recent[:5]:
                        parts = [
                            f"{r.get('pp_track_code','')} {r.get('pp_race_date','')[:10]}",
                            f"R{r.get('pp_race_number','')}",
                            f"Fin:{r.get('official_finish','')}",
                        ]
                        if r.get("speed_figure") is not None:
                            parts.append(f"SF:{r['speed_figure']}")
                        if r.get("pace_figure_1"):
                            parts.append(f"P1:{r['pace_figure_1']}")
                        if r.get("pace_figure_2"):
                            parts.append(f"P2:{r['pace_figure_2']}")
                        if r.get("class_rating"):
                            parts.append(f"CLS:{r['class_rating']}")
                        if r.get("short_comment"):
                            parts.append(f'"{r["short_comment"]}"')
                        pace_lines.append("  " + " | ".join(parts))
                    best_sf = max(sf_list) if sf_list else None
                    avg_sf = round(sum(sf_list) / len(sf_list), 1) if sf_list else None
                    summary_parts = [f"{len(pp_data)} starts in dataset"]
                    if best_sf is not None:
                        summary_parts.append(f"best speed fig {best_sf}")
                    if avg_sf is not None:
                        summary_parts.append(f"avg {avg_sf}")
                    pp_ctx = (
                        f"EQUIBASE PAST PERFORMANCES (2023 US PP data, Beyer-comparable scale):\n"
                        f"{horse_name} — {', '.join(summary_parts)}:\n"
                        + "\n".join(pace_lines)
                        + "\n(SF=speed figure, P1/P2=pace figures at calls, CLS=class rating)"
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
    SENT = 180   # one sentence
    PHRASE = 60  # short phrase

    data['race_summary'] = _trunc(data.get('race_summary', ''), SENT)
    data['pace_scenario'] = _trunc(data.get('pace_scenario', ''), SENT)
    data['overall_summary'] = _trunc(data.get('overall_summary', ''), SENT)

    la = data.get('longshot_alert') or {}
    la['reason'] = _trunc(la.get('reason', ''), SENT)

    for r in data.get('runners', []):
        r['summary'] = _trunc(r.get('summary', ''), SENT)
        r['strengths'] = [_trunc(s, PHRASE) for s in r.get('strengths', [])]
        r['weaknesses'] = [_trunc(s, PHRASE) for s in r.get('weaknesses', [])]

    for b in data.get('recommended_bets', []):
        b['reasoning'] = _trunc(b.get('reasoning', ''), SENT)

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
    _RACE_DROP = {"raw", "big_race", "type_of_race", "region", "pattern",
                  "age_band", "sex_restriction", "field_size"}
    slim = {k: v for k, v in race_data.items() if k not in _RACE_DROP and k != "runners"}
    slim["runners"] = [
        {k: v for k, v in r.items() if k not in _RUNNER_DROP and v not in (None, "", [])}
        for r in race_data.get("runners", [])
    ]
    return slim


async def analyze_race(race_data: dict, mode: str = "balanced", bankroll: float = None) -> dict:
    """
    Full race analysis — Secretariat's core function.
    Returns structured analysis of all runners and recommended bets.
    """
    runners = race_data.get("runners", [])
    ts_context = await get_hardware_and_historical_context(runners)

    ts_block = ""
    if ts_context:
        ts_block = "\n\nADDITIONAL HARDWARE DATA:\n" + "\n\n".join(ts_context.values())

    prompt = f"""Analyze this race. One sentence per field. Short phrases in arrays.

Race Data:
{json.dumps(_slim_race_for_prompt(race_data), indent=2)}{ts_block}

Mode: {mode} | Bankroll: {f'${bankroll:.2f}' if bankroll else 'unspecified'}

Return this JSON exactly:
{{
  "race_summary": "one sentence",
  "pace_scenario": "one sentence",
  "vulnerable_favorite": "horse name or null",
  "runners": [
    {{
      "horse_id": "id",
      "horse_name": "name",
      "contender_score": 0-100,
      "value_score": 0-100,
      "strengths": ["short phrase"],
      "weaknesses": ["short phrase"],
      "summary": "one sentence",
      "fair_odds": "e.g. 3/1",
      "recommended_bet": "win/place/show/avoid/use-in-exotics or null"
    }}
  ],
  "top_contenders": ["name1", "name2"],
  "longshot_alert": {{
    "horse_name": "name or null",
    "reason": "one sentence",
    "odds": "current odds"
  }},
  "recommended_bets": [
    {{
      "bet_type": "Win/Exacta/etc",
      "selection": "horse(s)",
      "reasoning": "one sentence",
      "suggested_stake": "e.g. $10",
      "risk_level": "low/medium/high"
    }}
  ],
  "overall_summary": "one sentence",
  "confidence": "low/medium/high"
}}"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    result = _truncate_analysis(_parse_json(response.content[0].text))
    try:
        await extract_and_store_fair_prices(race_data.get("race_id", ""), result)
    except Exception:
        pass
    return result


async def stream_analyze_race(race_data: dict, mode: str = "balanced", bankroll: float = None):
    """
    Async generator for streaming race analysis.
    Yields ("chunk", str) during generation, then ("result", dict) when done.
    """
    runners = race_data.get("runners", [])
    ts_context = await get_hardware_and_historical_context(runners)
    ts_block = "\n\nADDITIONAL HARDWARE DATA:\n" + "\n\n".join(ts_context.values()) if ts_context else ""

    prompt = f"""Analyze this race. One sentence per field. Short phrases in arrays.

Race Data:
{json.dumps(_slim_race_for_prompt(race_data), indent=2)}{ts_block}

Mode: {mode} | Bankroll: {f'${bankroll:.2f}' if bankroll else 'unspecified'}

Return this JSON exactly:
{{
  "race_summary": "one sentence",
  "pace_scenario": "one sentence",
  "vulnerable_favorite": "horse name or null",
  "runners": [
    {{
      "horse_id": "id",
      "horse_name": "name",
      "contender_score": 0-100,
      "value_score": 0-100,
      "strengths": ["short phrase"],
      "weaknesses": ["short phrase"],
      "summary": "one sentence",
      "fair_odds": "e.g. 3/1",
      "recommended_bet": "win/place/show/avoid/use-in-exotics or null"
    }}
  ],
  "top_contenders": ["name1", "name2"],
  "longshot_alert": {{
    "horse_name": "name or null",
    "reason": "one sentence",
    "odds": "current odds"
  }},
  "recommended_bets": [
    {{
      "bet_type": "Win/Exacta/etc",
      "selection": "horse(s)",
      "reasoning": "one sentence",
      "suggested_stake": "e.g. $10",
      "risk_level": "low/medium/high"
    }}
  ],
  "overall_summary": "one sentence",
  "confidence": "low/medium/high"
}}"""

    full_text = ""
    async with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            full_text += text
            yield ("chunk", text)

    result = _truncate_analysis(_parse_json(full_text))
    yield ("result", result)


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
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    return _parse_json(response.content[0].text)


async def score_horse(horse_data: dict, race_context: dict) -> dict:
    """
    Score a single horse across 6 dimensions for the Score Card.
    Returns structured JSON with scores 0-100 per dimension.
    """
    prompt = f"""Score this horse across exactly 6 handicapping dimensions.

Horse Data:
{json.dumps(horse_data, indent=2)}

Race Context:
{json.dumps(race_context, indent=2)}

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
- speed: based on speed figures, time comparisons, distance suitability
- class: based on race class history, level drops/rises, competition quality
- form: based on recent finishing positions, trajectory, consistency
- pace_fit: based on running style vs expected pace scenario in this race
- value: based on current odds vs estimated true probability (overlay=high score)
- trainer_jockey: based on trainer strike rate, jockey record, combo history

Be honest. A 50 is average. Reserve 80+ for genuinely strong attributes.
A horse can score 90 on speed and 20 on value — that's fine and useful."""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
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

    runners = race_data.get("runners", [])
    if not runners:
        return {"race_id": race_data.get("race_id", ""), "scorecards": []}

    race_context = {
        "race_id": race_data.get("race_id", ""),
        "course": race_data.get("course", ""),
        "distance": race_data.get("distance", ""),
        "surface": race_data.get("surface", ""),
        "going": race_data.get("going", ""),
        "race_class": race_data.get("race_class", ""),
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

    async def _score_safe(horse: dict) -> dict:
        try:
            return await score_horse(horse, race_context)
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

    return {
        "race_id": race_data.get("race_id", ""),
        "course": race_data.get("course", ""),
        "scorecards": list(scorecards)
    }


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
    """Free-form Q&A — user can ask Secretariat anything about horse racing."""
    prompt = f"""Racing Q&A. Answer in 2-4 sentences. Plain prose only — no bullet points, no bold, no dashes, no lists, no headers. Define jargon inline when needed.

Question: {question}
{"Context: " + json.dumps(context) if context else ""}

Return JSON: {{"answer": "2-4 sentence plain prose answer here"}}"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    parsed = _parse_json(response.content[0].text)
    return parsed.get("answer", "") if isinstance(parsed, dict) else str(parsed)
