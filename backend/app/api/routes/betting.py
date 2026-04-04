from fastapi import APIRouter, HTTPException

router = APIRouter()

# ---------------------------------------------------------------------------
# Odds conversion helpers
# ---------------------------------------------------------------------------

# (numerator, denominator) pairs ordered from shortest to longest price.
# Used to snap a decimal price to the nearest common fractional.
_COMMON_FRACTIONS = [
    (1,10),(1,5),(1,4),(2,7),(1,3),(2,5),(4,9),(1,2),(8,15),(4,7),(8,13),
    (4,6),(8,11),(4,5),(10,11),(1,1),(11,10),(6,5),(5,4),(6,4),(7,4),(2,1),
    (9,4),(5,2),(11,4),(3,1),(10,3),(4,1),(9,2),(5,1),(6,1),(7,1),(8,1),
    (9,1),(10,1),(12,1),(14,1),(16,1),(20,1),(25,1),(33,1),(50,1),(100,1),
]


def _fractional_to_decimal(frac: str) -> float:
    parts = frac.strip().split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid fractional odds: {frac}")
    return int(parts[0]) / int(parts[1]) + 1.0


def _decimal_to_fractional(dec: float) -> str:
    profit = dec - 1.0
    best = min(_COMMON_FRACTIONS, key=lambda f: abs(f[0] / f[1] - profit))
    return f"{best[0]}/{best[1]}"


def _american_to_decimal(american: int) -> float:
    if american >= 0:
        return american / 100.0 + 1.0
    return 100.0 / abs(american) + 1.0


def _decimal_to_american(dec: float) -> int:
    if dec >= 2.0:
        return round((dec - 1.0) * 100)
    return round(-100.0 / (dec - 1.0))


def _parse_odds(frac: str) -> float:
    """Parse a fractional odds string to decimal. Falls back to float cast."""
    try:
        return _fractional_to_decimal(frac)
    except (ValueError, ZeroDivisionError):
        return float(frac)


# ---------------------------------------------------------------------------
# Static bet types content
# ---------------------------------------------------------------------------

_BET_TYPES = {
    "single_bets": [
        {
            "type": "Win",
            "description": "Your horse must finish first to collect.",
            "risk": "medium",
            "best_for": "Confident selections with solid odds",
            "example": "£10 Win on Arkle at 5/1 returns £60 (£50 profit + £10 stake)",
        },
        {
            "type": "Place",
            "description": "Your horse must finish in the top 2, 3, or 4 places depending on field size.",
            "risk": "low",
            "best_for": "High-quality horses in competitive fields",
            "example": "£10 Place on 5/1 horse ≈ £10 at 5/4 = £22.50 return",
        },
        {
            "type": "Show",
            "description": "US equivalent of Place. Horse must finish in top 3.",
            "risk": "low",
            "best_for": "US racing, conservative bettors",
            "example": "£10 Show at 5/1 returns roughly £18–£22 depending on pool",
        },
        {
            "type": "Each Way",
            "description": "Two bets in one: Win + Place, each at half your stake.",
            "risk": "medium",
            "best_for": "Value horses at 8/1+ where a place pays",
            "example": "£10 EW = £5 Win + £5 Place. Win at 10/1, Place at 5/2 → £55 win + £17.50 place",
        },
    ],
    "exotic_bets": [
        {
            "type": "Exacta",
            "description": "Predict the first two finishers in exact order.",
            "risk": "high",
            "best_for": "Strong opinions on two horses",
            "example": "Exacta 1-3: Horse 1 wins, Horse 3 is second",
        },
        {
            "type": "Quinella",
            "description": "Predict the first two finishers in any order.",
            "risk": "medium",
            "best_for": "Two strong contenders when order is uncertain",
            "example": "Quinella 1/3: either order pays",
        },
        {
            "type": "Trifecta",
            "description": "Predict the first three finishers in exact order.",
            "risk": "high",
            "best_for": "Races where you can identify three clear horses",
            "example": "Box trifecta 1/2/3: any order of those three pays",
        },
        {
            "type": "Superfecta",
            "description": "Predict the first four finishers in exact order.",
            "risk": "very high",
            "best_for": "Large fields, lottery-style payoffs",
            "example": "£0.10 Superfecta box can be affordable with a $10 total",
        },
        {
            "type": "Daily Double",
            "description": "Pick the winner of two consecutive races.",
            "risk": "high",
            "best_for": "Two races you have strong opinions on",
            "example": "Races 3 & 4 winners in one bet",
        },
        {
            "type": "Pick 3",
            "description": "Pick the winner of three consecutive races.",
            "risk": "high",
            "best_for": "Multi-race sequences with clear standouts",
            "example": "Races 5, 6, 7 winners",
        },
        {
            "type": "Pick 4",
            "description": "Pick the winner of four consecutive races.",
            "risk": "very high",
            "best_for": "Bettors who study full cards",
        },
        {
            "type": "Pick 5",
            "description": "Pick the winner of five consecutive races.",
            "risk": "very high",
            "best_for": "Large pools, big potential payoffs",
        },
        {
            "type": "Pick 6",
            "description": "Pick the winner of six consecutive races. Carryover pools can be enormous.",
            "risk": "very high",
            "best_for": "Syndicate play, big cards like Cheltenham or Royal Ascot",
        },
    ],
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/odds/convert")
async def convert_odds(body: dict):
    stake = float(body.get("stake", 10.0))
    dec = None

    if "fractional" in body and body["fractional"]:
        try:
            dec = _fractional_to_decimal(str(body["fractional"]))
        except (ValueError, ZeroDivisionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    elif "decimal" in body and body["decimal"] is not None:
        dec = float(body["decimal"])

    elif "american" in body and body["american"] is not None:
        dec = _american_to_decimal(int(body["american"]))

    else:
        raise HTTPException(status_code=400, detail="Provide fractional, decimal, or american odds")

    if dec <= 1.0:
        raise HTTPException(status_code=400, detail="Decimal odds must be greater than 1.0")

    return {
        "fractional": _decimal_to_fractional(dec),
        "decimal": round(dec, 4),
        "american": _decimal_to_american(dec),
        "implied_probability": round(1.0 / dec * 100, 2),
        "profit_on_stake": round((dec - 1.0) * stake, 2),
        "total_return": round(dec * stake, 2),
        "stake": stake,
    }


@router.post("/payout/calculate")
async def calculate_payout(body: dict):
    bet_type = str(body.get("bet_type", "win")).lower()
    stake = float(body.get("stake", 10.0))
    odds_list: list = body.get("odds", [])
    each_way: bool = bool(body.get("each_way", False))

    if not odds_list:
        raise HTTPException(status_code=400, detail="Provide at least one odds value in 'odds' list")

    decimals = []
    for o in odds_list:
        try:
            decimals.append(_parse_odds(str(o)))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Cannot parse odds '{o}': {exc}") from exc

    if bet_type == "each_way" or each_way:
        win_dec = decimals[0]
        place_dec = (win_dec - 1.0) / 4.0 + 1.0
        est_return = (stake / 2.0) * win_dec + (stake / 2.0) * place_dec
        note = "Each Way: half stake win + half stake place at 1/4 odds"

    elif bet_type == "win":
        est_return = stake * decimals[0]
        note = "Win: full stake on horse to finish first"

    elif bet_type == "place":
        place_dec = (decimals[0] - 1.0) / 4.0 + 1.0
        est_return = stake * place_dec
        note = "Place: estimated at 1/4 win odds"

    elif bet_type == "show":
        place_dec = (decimals[0] - 1.0) / 5.0 + 1.0
        est_return = stake * place_dec
        note = "Show: estimated at 1/5 win odds"

    elif bet_type in ("exacta", "quinella"):
        product = 1.0
        for d in decimals[:2]:
            product *= d
        est_return = stake * product * 0.80
        note = f"{bet_type.capitalize()}: estimated with 20% takeout applied"

    elif bet_type == "trifecta":
        product = 1.0
        for d in decimals[:3]:
            product *= d
        est_return = stake * product * 0.75
        note = "Trifecta: estimated with 25% takeout applied"

    elif bet_type == "superfecta":
        product = 1.0
        for d in decimals[:4]:
            product *= d
        est_return = stake * product * 0.70
        note = "Superfecta: estimated with 30% takeout applied"

    else:
        est_return = stake * decimals[0]
        note = f"Estimated return for {bet_type} (treated as win)"

    return {
        "bet_type": bet_type,
        "stake": stake,
        "estimated_return": round(est_return, 2),
        "estimated_profit": round(est_return - stake, 2),
        "note": note,
    }


@router.get("/types")
async def bet_types():
    return _BET_TYPES
