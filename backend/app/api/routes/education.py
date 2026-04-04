from fastapi import APIRouter

router = APIRouter()

# ---------------------------------------------------------------------------
# Static content — defined once, served forever
# ---------------------------------------------------------------------------

_GLOSSARY = {
    "terms": [
        {"term": "Each Way", "definition": "A two-part bet: one on the horse to win, one on it to be placed (top 2, 3 or 4 depending on field size). Often abbreviated E/W."},
        {"term": "Form", "definition": "A horse's recent race results shown as a string of digits/letters, e.g. '1-2-F-3'. Most recent run is usually listed last."},
        {"term": "Going", "definition": "The condition of the racing surface. Ranges from Firm (fastest, driest) through Good, Good to Soft, Soft, to Heavy (slowest, wettest)."},
        {"term": "Handicap", "definition": "A race where horses carry different weights assigned by an official handicapper to equalise chances. Higher-rated horses carry more weight."},
        {"term": "SP", "definition": "Starting Price — the official odds of a horse at the moment the race starts. Bets placed without a fixed price are settled at SP."},
        {"term": "Morning Line", "definition": "The estimated odds published by the track before betting opens. Used as a guide; actual SP usually differs."},
        {"term": "Pari-Mutuel", "definition": "A betting pool system where all stakes are combined, the track takes its cut (takeout), and winners share what remains. Used in most countries."},
        {"term": "Takeout", "definition": "The percentage of the betting pool retained by the track/bookmaker before winnings are paid. Typically 14–25% in pari-mutuel racing."},
        {"term": "Overlay", "definition": "A horse whose true winning chance is better than its market price implies — a value bet."},
        {"term": "Underlay", "definition": "A horse whose market price is shorter (better for the bookmaker) than its actual winning chance warrants — poor value."},
        {"term": "Speed Figure", "definition": "A numerical rating of how fast a horse ran in a given race, adjusted for track variant and going. Allows comparison across different tracks and conditions."},
        {"term": "Beyer Speed Figure", "definition": "The most widely used speed figure in US racing, devised by Andrew Beyer. Published in the Daily Racing Form. Higher = faster."},
        {"term": "RPR", "definition": "Racing Post Rating — the UK/Ireland equivalent of the Beyer figure. Assigned by Racing Post handicappers after each run."},
        {"term": "Official Rating (OR)", "definition": "The weight-based handicap mark assigned by the British Horseracing Authority. Higher OR = higher class horse."},
        {"term": "Class", "definition": "The level of competition a horse runs at. Moving up in class (class rise) is a negative; dropping in class (class drop) is often a positive signal."},
        {"term": "Claiming Race", "definition": "A race where every horse is available to be purchased (claimed) at a declared price. Horses entered at lower prices are easier to claim but carry less weight."},
        {"term": "Allowance Race", "definition": "A non-claiming race above maiden level but below stakes. Entry conditions are based on age, earnings, or number of wins."},
        {"term": "Stakes Race", "definition": "The highest class of race. Horses are nominated and connections pay fees to enter. Graded stakes (G1, G2, G3) are the most prestigious."},
        {"term": "Furlong", "definition": "A unit of distance equal to 1/8 of a mile (201 metres). A 6-furlong race is 3/4 of a mile — sprint territory."},
        {"term": "Post Position", "definition": "The numbered starting stall/gate a horse draws. Can affect strategy, especially at certain tracks with rail bias."},
        {"term": "Pace", "definition": "The speed at which a race is run, particularly in the early and middle fractions. Influences which running styles (front-runners vs closers) are favoured."},
        {"term": "Trip", "definition": "A horse's passage through a race — whether it was hampered, found a clear run, was wide or boxed in. Good or bad trips explain form."},
        {"term": "Boxed", "definition": "Trapped on the rail with horses in front and beside — unable to find a clear run. A horse that 'got a box' was disadvantaged."},
        {"term": "Rail", "definition": "The inner fence of the track. Running along the rail can be advantageous or disadvantageous depending on track bias."},
        {"term": "Track Bias", "definition": "A consistent advantage for horses running in a particular part of the track (rail, wide) or using a particular running style (front-runners, closers)."},
        {"term": "Lay Off", "definition": "A period of time between a horse's races. Horses returning from long lay-offs are often fitter than their recent absence suggests — or need the run."},
        {"term": "Strike Rate", "definition": "The percentage of wins from total runs for a trainer, jockey, or sire. A high strike rate indicates form reliability."},
    ]
}

_BEGINNER_GUIDE = {
    "title": "GateSmart Beginner's Guide to Horse Racing Betting",
    "intro": "Horse racing can seem complicated, but the basics are simple. This guide walks you through everything you need to know to start betting with confidence.",
    "sections": [
        {
            "step": 1,
            "title": "The Basics: How a Race Works",
            "content": "Horses run around a track over a set distance. The first to cross the line wins. Distances are measured in furlongs (1 furlong = 201m / ~220 yards). A typical sprint is 5–7 furlongs; a middle-distance race is 1–1.5 miles; a marathon is 2+ miles.",
            "key_point": "Distance matters enormously. A sprinter and a stayer are completely different horses.",
        },
        {
            "step": 2,
            "title": "Win, Place, and Show — The Three Simple Bets",
            "content": "Win: your horse must finish first. Place: your horse must finish in the top 2 or 3 (varies by field size). Show (UK: Each Way): your horse must finish in the top 3 or 4. Place and Show pay less than a Win bet — lower risk, lower reward.",
            "key_point": "Start with Win bets. They're simple, honest, and teach you the most about reading races.",
        },
        {
            "step": 3,
            "title": "Reading a Race Card",
            "content": "A race card lists: horse name, age, weight, form string (e.g. 1-2-3-F), jockey, trainer, and current odds. The form string shows recent results (1=won, 2=second, F=fell, P=pulled up, U=unseated). Read right to left — most recent run is rightmost.",
            "key_point": "Fresh form is more valuable than old form. What happened 6 months ago matters less than last month.",
        },
        {
            "step": 4,
            "title": "Understanding Odds",
            "content": "Odds tell you two things: the payout and the implied probability. 5/1 fractional = 6.0 decimal = +500 American. A £10 Win bet at 5/1 returns £60 (£50 profit + £10 stake). Implied probability: 1 ÷ decimal odds. 5/1 → 1 ÷ 6.0 = 16.7% chance.",
            "key_point": "The favourite has the lowest odds and highest implied probability. It wins most often — but not always at value.",
        },
        {
            "step": 5,
            "title": "Bankroll Management",
            "content": "Never bet more than you can afford to lose. A sensible starting rule: never stake more than 2–5% of your total betting fund on a single race. If you have £100 to bet with, that's £2–5 per race. This keeps you in the game through losing runs.",
            "key_point": "Losing runs happen to everyone — even the best handicappers. Protect your bankroll and you'll always have another chance.",
        },
        {
            "step": 6,
            "title": "Finding Value — The Real Edge",
            "content": "Winning money long-term isn't about picking winners — it's about finding bets where the odds are better than the horse's true chance. If you think a horse has a 25% chance of winning but it's priced at 6/1 (14.3%), that's an overlay — a value bet. Bet overlays consistently and you'll profit over time.",
            "key_point": "A horse at 2/1 isn't automatically good value and a horse at 20/1 isn't automatically bad value. It's all about true probability vs price.",
        },
        {
            "step": 7,
            "title": "Using GateSmart's AI (Secretariat)",
            "content": "Secretariat analyses each race using form, pace, track conditions, class, and jockey/trainer stats. It gives every horse a Contender Score and Value Score, highlights the best bets, and flags longshots. Use it as your starting point — then apply your own judgement.",
            "key_point": "Secretariat explains its reasoning. If you understand why it likes a horse, you're learning handicapping — not just following tips.",
        },
    ],
    "golden_rules": [
        "Never chase losses with bigger bets",
        "Keep records of every bet — winners and losers",
        "Bet with a clear head — never when tired, drunk, or emotional",
        "Stick to your staking plan even during winning streaks",
        "Value beats volume — fewer, better-selected bets outperform betting everything",
        "Understand every bet before you place it",
    ],
}

_BANKROLL_GUIDE = {
    "title": "Bankroll Management for Horse Racing Bettors",
    "intro": "How you manage your money determines whether you last long enough to make a profit. Even with an edge, poor staking will wipe you out. Here are three proven strategies.",
    "strategies": [
        {
            "name": "Flat Staking",
            "summary": "Bet the same fixed amount on every selection.",
            "how_it_works": "Decide on a unit stake (e.g. £10 or 2% of your bankroll) and stick to it regardless of how confident you feel or what the odds are.",
            "pros": ["Simple to implement", "Limits emotional over-betting", "Easy to track profit/loss"],
            "cons": ["Doesn't account for varying levels of confidence", "Misses opportunities to press advantage on high-confidence bets"],
            "best_for": "Beginners and anyone who tends to overtrade when confident.",
            "example": "£500 bankroll → £10 flat stake per bet. After 50 bets you can review P&L clearly.",
        },
        {
            "name": "Percentage Staking",
            "summary": "Bet a fixed percentage of your current bankroll each time.",
            "how_it_works": "Choose a percentage (typically 1–3%). Your stake rises when you're winning and falls when you're losing, naturally protecting against ruin.",
            "pros": ["Self-adjusting — protects bankroll during losing runs", "Scales up organically as you grow", "Mathematically sounder than flat staking"],
            "cons": ["Stakes shrink during losing runs which can feel frustrating", "More complex to calculate"],
            "best_for": "Intermediate bettors with a proven edge who want sustainable growth.",
            "example": "£500 bankroll at 2% = £10 stake. After growing to £600, stake becomes £12. After a loss back to £550, stake becomes £11.",
        },
        {
            "name": "Kelly Criterion",
            "summary": "Mathematical formula that calculates the optimal bet size based on your edge.",
            "how_it_works": "Formula: Stake % = (bp - q) / b, where b = decimal odds - 1, p = your estimated win probability, q = 1 - p. Only bet when Kelly gives a positive value.",
            "pros": ["Mathematically optimal for long-run bankroll growth", "Forces you to quantify your edge before betting", "Maximises growth rate"],
            "cons": ["Requires accurate probability estimation — hard in practice", "Full Kelly can produce large swings; most use Half Kelly (divide result by 2)", "Over-betting is catastrophic — errors are expensive"],
            "best_for": "Experienced bettors who can accurately assess win probabilities.",
            "example": "Horse at 5/1 (decimal 6.0), you estimate 25% chance. Kelly: (5 × 0.25 - 0.75) / 5 = 0.10 = 10% of bankroll. Half Kelly: 5%.",
        },
    ],
    "session_rules": [
        "Set a session loss limit before you start (e.g. stop if you lose 20% of bankroll in one day)",
        "Set a win target too — locking in profits prevents giving it all back",
        "Never top up your betting fund from non-betting money mid-session",
        "Review your betting log weekly — look for patterns in what's working",
        "Adjust your staking plan quarterly based on actual results, not gut feel",
        "If you're on tilt (frustrated, chasing), stop for the day",
    ],
}


@router.get("/glossary")
async def glossary():
    return _GLOSSARY


@router.get("/beginner-guide")
async def beginner_guide():
    return _BEGINNER_GUIDE


@router.get("/bankroll-guide")
async def bankroll_guide():
    return _BANKROLL_GUIDE
