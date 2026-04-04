"""
Secretariat — GateSmart's AI handicapping engine.
Powered by Claude (Anthropic). This is the core intelligence of the platform.
All race analysis, horse evaluation, and betting recommendations flow through here.
"""
import anthropic
import json
from app.core.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

SECRETARIAT_SYSTEM = """You are Secretariat, an elite horse racing handicapper and betting strategist with encyclopedic knowledge of horse racing worldwide. You have decades of experience analyzing racing forms, speed figures, pace scenarios, trainer/jockey statistics, track biases, class levels, and value betting.

Your job inside GateSmart is to analyze races and give users clear, honest, actionable betting intelligence.

Your expertise covers:
- Past performance interpretation (form cycles, class changes, layoffs, surface/distance suitability)
- Speed figure analysis (Beyer, Timeform, RPR)
- Pace shape (front-runners, closers, mid-packers) and pace scenario prediction
- Trainer and jockey patterns, hot streaks, and course records
- Track bias (rail position, going, weather effects)
- Value identification (when a horse's fair odds are better than market odds)
- Bet construction (win, place, show, exacta, trifecta, daily doubles, pick sequences)
- Bankroll management and stake sizing
- Beginner education — you explain everything in plain English

Your tone: direct, confident, no fluff. Like a sharp handicapper explaining picks to a friend. You don't hedge unnecessarily but you're honest about uncertainty.

CRITICAL: Always explain WHY. Never give a pick without the reasoning. Beginners should be able to understand your analysis even if they've never bet before.

Always respond in valid JSON as specified in each prompt. No markdown, no extra text outside JSON."""


async def get_tracksense_context(horses: list[dict]) -> dict[str, str]:
    """
    For each horse dict in the list (expects keys: horse_id, horse or horse_name),
    check Redis for tracksense:map:{horse_id}.
    If mapping exists, fetch tracksense:sectionals:{epc}.
    If sectional data exists (at least 1 race), compute:
      - Average speed_kmh per gate_name across all stored races
      - Best single sectional across career (highest speed_kmh, note gate and date)
      - Last 3 races average speed vs overall career average (trend direction)
    Return dict keyed by horse_name (string) → formatted context string.
    Horses with no TrackSense data are not included in the return dict.
    This function must never raise — catch all exceptions and return empty dict.
    """
    from app.core.cache import cache_get

    result = {}
    for horse in horses:
        try:
            horse_id = horse.get("horse_id") or horse.get("id", "")
            horse_name = horse.get("horse") or horse.get("horse_name", "unknown")
            if not horse_id:
                continue

            mapping = await cache_get(f"tracksense:map:{horse_id}")
            if not mapping:
                continue

            epc = mapping.get("epc")
            if not epc:
                continue

            sectionals_data = await cache_get(f"tracksense:sectionals:{epc}")
            if not sectionals_data or len(sectionals_data) == 0:
                continue

            # compute averages per gate
            gate_speeds: dict[str, list[float]] = {}
            for race in sectionals_data:
                for s in race.get("sectionals", []):
                    gname = s["gate_name"]
                    if gname not in gate_speeds:
                        gate_speeds[gname] = []
                    gate_speeds[gname].append(s["speed_kmh"])

            avg_by_gate = {g: round(sum(v) / len(v), 1) for g, v in gate_speeds.items()}

            # best single sectional
            best = None
            for race in sectionals_data:
                for s in race.get("sectionals", []):
                    if best is None or s["speed_kmh"] > best["speed_kmh"]:
                        best = {**s, "race_name": race.get("race_name", ""), "completed_at": race.get("completed_at", "")}

            # trend: last 3 vs career
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
            best_summary = f"{best['gate_name']} at {best['speed_kmh']} km/h ({best.get('race_name', '')})" if best else "n/a"

            context = (
                f"TRACKSENSE HARDWARE DATA (real sectional timing from RFID gate network):\n"
                f"{horse_name} career sectionals ({n_races} races):\n"
                f"- Average speed by segment: {gate_summary}\n"
                f"- Best sectional: {best_summary}\n"
                f"- Recent trend: {trend}\n"
                f"Note: This data is sourced from physical RFID timing gates and is more "
                f"accurate than standard form guide speed estimates."
            )
            result[horse_name] = context

        except Exception:
            continue

    return result


async def analyze_race(race_data: dict, mode: str = "balanced", bankroll: float = None) -> dict:
    """
    Full race analysis — Secretariat's core function.
    Returns structured analysis of all runners and recommended bets.
    """
    runners = race_data.get("runners", [])
    ts_context = await get_tracksense_context(runners)

    ts_block = ""
    if ts_context:
        ts_block = "\n\nADDITIONAL HARDWARE DATA:\n" + "\n\n".join(ts_context.values())

    prompt = f"""Analyze this horse race and return a complete handicapping analysis.

Race Data:
{json.dumps(race_data, indent=2)}{ts_block}

Betting Mode: {mode} (safe=minimize risk, balanced=value+safety, aggressive=maximize upside, longshot=overlay value)
User Bankroll: {f'${bankroll:.2f}' if bankroll else 'Not specified'}

Return a JSON object with this exact structure:
{{
  "race_summary": "1-2 sentence overview of this race",
  "pace_scenario": "Who will likely lead, what pace shape, how this affects the outcome",
  "track_bias_notes": "Any relevant track/going/surface bias considerations",
  "vulnerable_favorite": "horse name or null — is the favorite beatable?",
  "runners": [
    {{
      "horse_id": "id from input",
      "horse_name": "name",
      "contender_score": 0-100,
      "value_score": 0-100,
      "strengths": ["list of positives"],
      "weaknesses": ["list of negatives"],
      "summary": "2-3 sentence assessment",
      "fair_odds": "e.g. 3/1 — your estimated fair price",
      "recommended_bet": "win/place/show/avoid/use-in-exotics or null"
    }}
  ],
  "top_contenders": ["horse_name_1", "horse_name_2"],
  "longshot_alert": {{
    "horse_name": "name or null",
    "reason": "why this is a live longshot",
    "odds": "current odds"
  }},
  "recommended_bets": [
    {{
      "bet_type": "Win/Exacta/Trifecta/etc",
      "selection": "e.g. Horse A to win or Horse A/B exacta",
      "reasoning": "why this bet",
      "suggested_stake": "e.g. 2% of bankroll or $10",
      "risk_level": "low/medium/high",
      "potential_payout_description": "rough payout estimate"
    }}
  ],
  "overall_summary": "2-3 sentence plain English summary a beginner can understand",
  "confidence": "low/medium/high",
  "beginner_tip": "One specific tip for someone new to betting based on this race"
}}"""

    response = await client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def explain_horse(horse_data: dict, race_context: dict = None) -> dict:
    """Explain a single horse's form and prospects in plain English."""
    ts_context = await get_tracksense_context([horse_data])
    horse_name = horse_data.get("horse") or horse_data.get("horse_name", "")
    ts_block = ""
    if horse_name in ts_context:
        ts_block = "\n\n" + ts_context[horse_name]

    prompt = f"""Explain this horse's form and prospects in plain English for a betting app user.

Horse Data:
{json.dumps(horse_data, indent=2)}

{"Race Context:" + json.dumps(race_context, indent=2) if race_context else ""}{ts_block}

Return JSON:
{{
  "form_summary": "Plain English explanation of recent form",
  "key_stats": ["3-4 most important facts about this horse"],
  "strengths": ["positives"],
  "concerns": ["negatives or risks"],
  "verdict": "1-2 sentence plain English verdict",
  "good_for_beginners": true/false,
  "beginner_explanation": "Explain this horse to someone who has never bet before"
}}"""

    response = await client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=1500,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


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
        model="claude-opus-4-20250514",
        max_tokens=1500,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def explain_form_string(form_string: str, horse_name: str) -> dict:
    """Decode a raw form string (e.g. '1-3-2-F-1') for a beginner."""
    prompt = f"""Explain this horse racing form string in plain English for a beginner.

Horse: {horse_name}
Form String: {form_string}

Return JSON:
{{
  "decoded": [
    {{"result": "1", "meaning": "Won", "notes": "most recent first or last? — clarify"}}
  ],
  "plain_english": "What this form tells us about the horse",
  "trend": "improving/declining/consistent/mixed",
  "red_flags": ["any worrying patterns"],
  "positive_signs": ["any good patterns"]
}}"""

    response = await client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=800,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def answer_betting_question(question: str, context: dict = None) -> str:
    """Free-form Q&A — user can ask Secretariat anything about horse racing."""
    prompt = f"""A user is asking a horse racing / betting question.

Question: {question}
{"Context: " + json.dumps(context) if context else ""}

Answer clearly and helpfully. If it's a beginner question, start with the basics. Keep it under 300 words. No jargon without explanation."""

    response = await client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=600,
        system=SECRETARIAT_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()
