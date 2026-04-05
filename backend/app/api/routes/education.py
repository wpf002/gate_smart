from fastapi import APIRouter

router = APIRouter()

# ---------------------------------------------------------------------------
# Static content — US-first, with international context where relevant
# ---------------------------------------------------------------------------

_GLOSSARY = {
    "terms": [
        # ── US BET TYPES ────────────────────────────────────────────────────
        {"term": "Win", "definition": "Your horse must finish first. The most straightforward bet. If your horse wins, you collect; otherwise you lose your stake.", "category": "Bet Types"},
        {"term": "Place", "definition": "Your horse must finish first or second. Pays less than a win bet but easier to cash.", "category": "Bet Types"},
        {"term": "Show", "definition": "Your horse must finish first, second, or third. Lowest payout of the straight bets but highest probability of cashing.", "category": "Bet Types"},
        {"term": "Across the Board", "definition": "Three simultaneous bets: Win + Place + Show on the same horse. Triple the stake, but you collect on any of the three bets that hit.", "category": "Bet Types"},
        {"term": "Exacta (Perfecta)", "definition": "Pick the first and second place finishers in exact order. Higher payout than straight bets. A Box Exacta covers both orders for double the cost.", "category": "Bet Types"},
        {"term": "Trifecta", "definition": "Pick the first, second, and third place finishers in exact order. Difficult but can pay very large sums. Box or wheel to increase coverage.", "category": "Bet Types"},
        {"term": "Superfecta", "definition": "Pick the first four finishers in exact order. Extremely difficult — $0.10 minimum at many US tracks lets you play multiple combinations cheaply.", "category": "Bet Types"},
        {"term": "Daily Double", "definition": "Pick the winners of two consecutive races (usually races 1&2, or the last two races). Must select both correctly.", "category": "Bet Types"},
        {"term": "Pick 3", "definition": "Select the winner of three consecutive races. Minimum usually $0.50 or $1.", "category": "Bet Types"},
        {"term": "Pick 4", "definition": "Select the winner of four consecutive races. Often run as a carryover sequence with large jackpot pools.", "category": "Bet Types"},
        {"term": "Pick 5", "definition": "Select the winner of five consecutive races. Typically has a 50-cent minimum and large carryover pools.", "category": "Bet Types"},
        {"term": "Pick 6", "definition": "Select the winner of six consecutive races. The hardest and highest-paying exotic bet. Mandatory payout on the final day of a race meet.", "category": "Bet Types"},
        {"term": "Wheel", "definition": "Using one or more horses in one leg of a multi-race bet while covering all others in the remaining legs. e.g., 'wheel the 3 with all in the double.'", "category": "Bet Types"},
        {"term": "Box", "definition": "Covering all combinations of your selected horses in an exacta, trifecta, or superfecta. A 3-horse exacta box covers all 6 possible orders.", "category": "Bet Types"},
        {"term": "Key Horse", "definition": "A single horse you use in every combination of an exotic bet. e.g., '3 key with 1, 2, 4 in the trifecta' means 3 must win, others fill 2nd/3rd.", "category": "Bet Types"},
        {"term": "Each Way (UK/Ireland)", "definition": "A two-part bet: Win + Place. Standard in UK/Irish betting, roughly equivalent to US Win + Place bets combined.", "category": "Bet Types"},

        # ── RACE TYPES ──────────────────────────────────────────────────────
        {"term": "Maiden Race", "definition": "A race restricted to horses that have never won. Maiden Special Weight (MSW) is for unraced/lightly raced horses; Maiden Claiming is lower quality.", "category": "Race Types"},
        {"term": "Maiden Special Weight (MSW)", "definition": "The entry-level race for unproven horses carrying standard weights. Winning an MSW is the first step up the class ladder.", "category": "Race Types"},
        {"term": "Claiming Race", "definition": "Any horse in the race can be purchased (claimed) for the stated claiming price. Lower claiming prices = lower class. A $10,000 claimer is much weaker than a $100,000 claimer.", "category": "Race Types"},
        {"term": "Allowance Race", "definition": "Non-claiming race above maiden level. Entry is based on conditions like age, sex, or number of wins. Better horses than claimers, below stakes.", "category": "Race Types"},
        {"term": "Optional Claimer", "definition": "A race that can be entered as an allowance OR as a claimer. Horses entered to be claimed are usually at a disadvantage.", "category": "Race Types"},
        {"term": "Stakes Race", "definition": "The top tier of racing. Horses are nominated by owners who pay entry fees. Graded Stakes (G1, G2, G3) are the most prestigious. G1 is the highest.", "category": "Race Types"},
        {"term": "Grade 1 (G1)", "definition": "The highest classification of race. Examples: Kentucky Derby, Breeders' Cup Classic, Belmont Stakes, Preakness Stakes.", "category": "Race Types"},
        {"term": "Grade 2 (G2)", "definition": "Second tier stakes race. Highly competitive — G2 winners are often G1 contenders.", "category": "Race Types"},
        {"term": "Grade 3 (G3)", "definition": "Third tier stakes race. Often used as prep races for bigger spots. Winning a G3 is still a significant accomplishment.", "category": "Race Types"},
        {"term": "Handicap Race", "definition": "Horses carry different weights assigned by the track handicapper to equalize chances. Higher-rated horses carry more weight. Common in UK/Ireland.", "category": "Race Types"},
        {"term": "Starter Allowance / Starter Handicap", "definition": "A race for horses that have previously started in a claiming race at or below a certain price. A step up from claiming, below open allowance.", "category": "Race Types"},

        # ── SPEED & FORM ─────────────────────────────────────────────────────
        {"term": "Beyer Speed Figure", "definition": "The gold standard US speed rating, devised by handicapper Andrew Beyer. Published in Daily Racing Form. Adjusts for track speed (variant). Higher = faster. A 100+ Beyer is elite; below 60 is low-level.", "category": "Speed & Form"},
        {"term": "TimeForm Rating", "definition": "UK/Ireland equivalent of Beyer. Numerical rating on a 0–145+ scale. 130+ is top-class; 100+ is stakes-level.", "category": "Speed & Form"},
        {"term": "RPR", "definition": "Racing Post Rating — UK/Ireland horse quality rating assigned by Racing Post handicappers after each run.", "category": "Speed & Form"},
        {"term": "Speed Figure", "definition": "Any numerical rating of how fast a horse ran, adjusted for track condition and bias. Allows comparison across different tracks and surfaces.", "category": "Speed & Form"},
        {"term": "Track Variant", "definition": "A correction applied to a day's times to account for whether the track was playing fast or slow. Essential for accurate speed figures.", "category": "Speed & Form"},
        {"term": "Form String", "definition": "A horse's recent results shown as a sequence, oldest to newest. In the US: 1=win, 2–9=finishing position. UK uses same plus P=pulled up, F=fell. '-' or '/' = season break.", "category": "Speed & Form"},
        {"term": "Last Run / Days Since Last Race", "definition": "How many days since the horse's most recent race. Horses returning after 60+ days are 'freshened.' Can be a positive (rested) or negative (rusty) depending on trainer patterns.", "category": "Speed & Form"},
        {"term": "Workout", "definition": "A timed training run at the track. Bullet workouts (fastest of the day at a distance) are a positive sign. Reported in the Daily Racing Form as 'blowouts' (short) or full works.", "category": "Speed & Form"},

        # ── PACE & RUNNING STYLE ─────────────────────────────────────────────
        {"term": "Pace", "definition": "The speed at which the early fractions of a race are run. Affects which running styles (front-runners vs closers) are favoured.", "category": "Pace"},
        {"term": "Pace Figures (E1, E2, Late Pace)", "definition": "Numerical ratings for a horse's early speed (E1 = first call, E2 = second call) and finishing kick (Late Pace). Used to predict pace shape.", "category": "Pace"},
        {"term": "Front-Runner (Wire-to-Wire)", "definition": "A horse that goes to the lead immediately and tries to hold it all the way. Vulnerable in fast-pace scenarios.", "category": "Pace"},
        {"term": "Presser", "definition": "A horse that runs just off the lead, close to the front. Often gets the best of both worlds — conserves energy, still benefits from a clear path.", "category": "Pace"},
        {"term": "Stalker", "definition": "A horse that tracks the pace from mid-pack, then makes a sustained run at the leaders in the stretch.", "category": "Pace"},
        {"term": "Closer / Stretch Runner", "definition": "A horse that drops far back early and makes a big run at the end. Needs pace meltdown scenarios to win.", "category": "Pace"},
        {"term": "Lone Speed", "definition": "When only one horse in the race wants to go to the front. A massive advantage — that horse can dictate a slow pace and hold off closers.", "category": "Pace"},
        {"term": "Pace Scenario", "definition": "The predicted flow of a race based on which horses want to run early. Contested pace (multiple front-runners) often sets up closers; uncontested pace sets up the lone speed horse.", "category": "Pace"},

        # ── TRACK & CONDITIONS ───────────────────────────────────────────────
        {"term": "Track Bias", "definition": "A consistent advantage for horses running in a specific part of the track (inside rail, outside path) or using a specific running style. Must be identified and exploited.", "category": "Track & Conditions"},
        {"term": "Rail Bias", "definition": "When horses running on the inside (rail) have a consistent advantage or disadvantage. Varies by track and weather.", "category": "Track & Conditions"},
        {"term": "Fast (Going)", "definition": "US dirt track condition — firm, dry surface. Favours front-runners and speed horses. Opposite of Sloppy.", "category": "Track & Conditions"},
        {"term": "Good (Going)", "definition": "Slightly slower than Fast on dirt, or firm-leaning on turf. Good conditions suit most running styles.", "category": "Track & Conditions"},
        {"term": "Sloppy (Going)", "definition": "Wet dirt surface with water sitting on top. Tends to favour front-runners. Some horses love slop; others hate it.", "category": "Track & Conditions"},
        {"term": "Muddy (Going)", "definition": "Wet, saturated dirt. Slower than Sloppy, favours strong, grinding horses. Mud-lovers are a real category.", "category": "Track & Conditions"},
        {"term": "Sealed (Track)", "definition": "A wet track that has been packed down (sealed) by a roller. Plays differently from a natural wet track — often favors speed.", "category": "Track & Conditions"},
        {"term": "Firm (Turf)", "definition": "Fast turf condition — dry and hard. Favors horses with good form on firm going.", "category": "Track & Conditions"},
        {"term": "Yielding (Turf)", "definition": "Soft turf with give. Requires more stamina. Some turf specialists prefer it; others don't handle it.", "category": "Track & Conditions"},
        {"term": "Off Track", "definition": "Any wet or compromised dirt track condition (Sloppy, Muddy, etc). Checking a horse's off-track record is essential before betting in bad weather.", "category": "Track & Conditions"},
        {"term": "Turf vs Dirt", "definition": "Horses often perform very differently on grass (turf) vs dirt. A horse switching surfaces for the first time is an unknown — trainer pattern and workouts become crucial.", "category": "Track & Conditions"},

        # ── CLASS & RATINGS ──────────────────────────────────────────────────
        {"term": "Class", "definition": "The competitive level a horse runs at. The class ladder from bottom to top: Maiden Claiming → Maiden Special Weight → Claiming → Allowance → Stakes → Graded Stakes.", "category": "Class & Ratings"},
        {"term": "Class Rise / Drop", "definition": "Moving up in class after a win (class rise) is a negative — can a horse handle tougher competition? Dropping in class (class drop) is typically a positive sign.", "category": "Class & Ratings"},
        {"term": "Official Rating (OR)", "definition": "UK/Ireland numerical handicap mark. Higher = better horse. Used to assign weights in handicap races.", "category": "Class & Ratings"},
        {"term": "Layoff / Freshening", "definition": "Extended time between races. Trainers 'freshen' horses to let them recover physically. Some trainers (Chad Brown, Bob Baffert) excel with freshened horses.", "category": "Class & Ratings"},

        # ── ODDS & VALUE ─────────────────────────────────────────────────────
        {"term": "American Odds (Moneyline)", "definition": "US standard odds format. +500 means you win $500 on a $100 bet. -200 means you must bet $200 to win $100. Positive = underdog, negative = favorite.", "category": "Odds & Value"},
        {"term": "Fractional Odds", "definition": "UK standard: 5/1 means win $5 for every $1 staked. 5/2 means win $5 for every $2 staked. Evens (1/1) means double your money.", "category": "Odds & Value"},
        {"term": "Decimal Odds", "definition": "European standard: 6.0 means get back $6 for every $1 bet (including stake). Convert from fractional: (numerator/denominator) + 1.", "category": "Odds & Value"},
        {"term": "Morning Line", "definition": "Estimated odds set by the track handicapper before betting opens. Not a prediction — a rough guide. Actual odds shift based on betting action.", "category": "Odds & Value"},
        {"term": "Tote / Pari-Mutuel", "definition": "US betting system where all bets go into a pool, the track takes its cut (takeout), and remaining money is divided among winners. Odds aren't fixed until the race goes off.", "category": "Odds & Value"},
        {"term": "Takeout", "definition": "The percentage the track keeps from each betting pool. Win/Place/Show: ~17–18%. Exotics: 20–25%. Lower takeout = better value for bettors.", "category": "Odds & Value"},
        {"term": "SP (Starting Price)", "definition": "The final odds when the race begins. UK/Ireland standard for settling bets without a fixed price.", "category": "Odds & Value"},
        {"term": "Overlay", "definition": "A horse priced higher (longer odds) than its true probability warrants — a value bet. If you think a horse has a 25% chance but it's 6/1 (14%), it's an overlay.", "category": "Odds & Value"},
        {"term": "Underlay", "definition": "A horse priced lower (shorter odds) than its true probability warrants — poor value. The public favorite is often underlaid.", "category": "Odds & Value"},
        {"term": "Dead Heat", "definition": "A tie between two or more horses at the finish line. Winnings are split proportionally.", "category": "Odds & Value"},

        # ── TRAINER / JOCKEY ─────────────────────────────────────────────────
        {"term": "Jockey", "definition": "The rider. In the US, top jockeys include Irad Ortiz Jr., Flavien Prat, John Velazquez, Luis Saez, Tyler Gaffalione. Jockey changes — especially to a better rider — are meaningful.", "category": "Trainer & Jockey"},
        {"term": "Trainer", "definition": "The person responsible for a horse's preparation. Top US trainers: Chad Brown (turf specialist), Bob Baffert (classic horses), Todd Pletcher, Bill Mott, Brad Cox. Trainer patterns matter enormously.", "category": "Trainer & Jockey"},
        {"term": "Trainer Stats (14-day)", "definition": "Win percentage and starts over the past 14 days. A trainer on a hot streak often indicates horses are in top form.", "category": "Trainer & Jockey"},
        {"term": "Claimed", "definition": "When a horse is purchased from a claiming race by a new owner. A claim can signal a trainer upgrade — or a trainer dumping a problem horse.", "category": "Trainer & Jockey"},
        {"term": "First-Time Starter (Debut)", "definition": "A horse making its first career start. Workouts and trainer/jockey stats are the only data available. Top trainers win at high rates with debut horses.", "category": "Trainer & Jockey"},
        {"term": "Shipper", "definition": "A horse traveling from a different track or jurisdiction to run. Can be a positive (fresh angles, class change) or negative (tired from travel).", "category": "Trainer & Jockey"},

        # ── EQUIPMENT ────────────────────────────────────────────────────────
        {"term": "Blinkers", "definition": "Equipment placed around a horse's eyes to restrict its field of vision, keeping it focused. Adding blinkers first time (BTB) is often a positive sign.", "category": "Equipment"},
        {"term": "Lasix (Furosemide)", "definition": "A medication used to prevent exercise-induced pulmonary hemorrhage (bleeding). Horses racing on Lasix for the first time often run better.", "category": "Equipment"},
        {"term": "Tongue Tie", "definition": "A strap securing the tongue to prevent airway obstruction. Can improve a horse's breathing and performance.", "category": "Equipment"},
        {"term": "Headgear", "definition": "Any equipment worn on a horse's head: blinkers, hoods, visors, cheekpieces. Changes in headgear often signal a trainer's attempt to improve performance.", "category": "Equipment"},

        # ── RACE RESULT TERMS ────────────────────────────────────────────────
        {"term": "Lengths", "definition": "The unit of distance between finishing horses. One length ≈ 8–9 feet. A horse winning by 3 lengths beat the runner-up by roughly 24 feet.", "category": "Race Results"},
        {"term": "Neck / Head / Nose", "definition": "Narrow winning margins, in decreasing order. A nose is the smallest possible winning margin.", "category": "Race Results"},
        {"term": "Disqualified (DQ)", "definition": "A horse placed first by the stewards but later disqualified for interference, a positive drug test, or other violation. Results are revised.", "category": "Race Results"},
        {"term": "Scratched", "definition": "A horse withdrawn from a race after being entered. Can happen for health, weather, or track condition reasons.", "category": "Race Results"},
        {"term": "Also-Ran", "definition": "A horse that finished outside the money positions (usually 4th or worse). Not relevant for straight bets but may be used in exotic combinations.", "category": "Race Results"},
        {"term": "Photo Finish", "definition": "When two or more horses finish too close to determine the winner by eye. A camera at the finish line determines the result.", "category": "Race Results"},
        {"term": "Inquiry / Objection", "definition": "A stewards' review of a race for possible interference. The result may be revised pending the inquiry.", "category": "Race Results"},
    ]
}

_BEGINNER_GUIDE = {
    "title": "GateSmart Beginner's Guide to US Horse Racing Betting",
    "intro": "Horse racing at American tracks is one of the oldest and most exciting sports in the country. This guide walks you through everything you need to start betting with confidence at tracks like Churchill Downs, Belmont Park, Saratoga, Keeneland, and Santa Anita.",
    "sections": [
        {
            "step": 1,
            "title": "How a Race Works",
            "content": "Horses break from numbered starting gates and race around a dirt or turf track over a set distance. First to the wire wins. Distances are measured in furlongs — 1 furlong = 1/8 of a mile = 220 yards. A 6-furlong sprint takes about 1 minute 10 seconds. The Kentucky Derby is 1.25 miles (10 furlongs). Most US races are between 5.5 and 9 furlongs.",
            "key_point": "Know the distance. A horse that dominates 6-furlong sprints may struggle going 1 mile 1/8. Distance suitability is one of the most important factors.",
        },
        {
            "step": 2,
            "title": "The Three Straight Bets: Win, Place, Show",
            "content": "WIN: Your horse must finish first. Full payout.\nPLACE: Your horse must finish 1st or 2nd. Lower payout than Win, but easier to cash.\nSHOW: Your horse must finish 1st, 2nd, or 3rd. Lowest payout but highest chance of cashing.\n\nAcross the Board means betting Win + Place + Show on the same horse. If your horse wins, you collect all three. If it runs 3rd, you collect only Show.",
            "key_point": "Start with Win bets. They pay the most and teach you the most about handicapping.",
        },
        {
            "step": 3,
            "title": "Exotic Bets: Exacta, Trifecta, Superfecta",
            "content": "EXACTA: Name the 1st and 2nd place finishers in order. Typical minimum: $2.\nTRIFECTA: Name 1st, 2nd, and 3rd in order. Minimum: $1.\nSUPERFECTA: Name 1st, 2nd, 3rd, and 4th in order. Minimum: $0.10 (yes, ten cents!)\n\nUse BOX bets to cover multiple combinations. A $1 exacta box with horses 3 and 5 costs $2 total and covers both 3-5 and 5-3.",
            "key_point": "The $0.10 superfecta is one of the best value plays in racing — small stake, massive potential payout.",
        },
        {
            "step": 4,
            "title": "Multi-Race Bets: Daily Double, Pick 3, Pick 4, Pick 5, Pick 6",
            "content": "Pick the winner of consecutive races. Minimum bets are usually $0.50–$2. The Pick 6 (six winners in a row) often has a mandatory payout if no one hits all six, creating massive pool sizes. Use a 'wheel' to put one strong horse with multiple options in other legs.",
            "key_point": "Multi-race bets offer the biggest paydays but require patience and bankroll management. Start with the Daily Double.",
        },
        {
            "step": 5,
            "title": "Reading US Odds",
            "content": "American odds show how much you win on a $2 bet (the standard minimum). Odds of 3-1 mean you win $6 for a $2 bet ($4 profit + $2 stake back). The morning line is the track handicapper's estimate before betting opens — actual odds shift based on how the crowd bets. The horse with the lowest odds is the favorite.",
            "key_point": "The favorite wins about 33% of the time in US racing. That means they lose 67% of the time — there's always opportunity against them.",
        },
        {
            "step": 6,
            "title": "Beyer Speed Figures — Your Most Important Tool",
            "content": "Beyer Speed Figures (published in the Daily Racing Form) are the gold standard for comparing how fast horses run. A horse with a 95 Beyer in its last race ran significantly faster than one with an 82. Elite horses run 100+. Allowance horses: 80-95. Claimers: 60-79. The catch: one big figure doesn't make a horse. Look for consistency.",
            "key_point": "A horse with consistent 90+ Beyers entered in a field of 78s is a serious contender. Class and pace matter too, but Beyers are your baseline.",
        },
        {
            "step": 7,
            "title": "Class — The Most Underrated Factor",
            "content": "The class ladder from bottom to top: Maiden Claiming → Maiden Special Weight → Claiming → Allowance → Optional Claimer → Stakes → Graded Stakes (G3, G2, G1). A horse dropping from a $50,000 claimer to a $25,000 claimer is a class drop — often a positive sign. A horse moving from an allowance to a G3 stakes is a big class rise — a negative unless it has shown top-class ability.",
            "key_point": "Class drops are betting opportunities. When a horse tries a lower level than it's been running, it's often physically compromised — but the trainer still thinks it can win there.",
        },
        {
            "step": 8,
            "title": "Using GateSmart (Secretariat)",
            "content": "Secretariat analyzes each race using form, Beyer figures, pace scenarios, trainer/jockey stats, and track bias. It gives every horse a Contender Score and Value Score, highlights the best bets, and flags live longshots. Use it as your starting point. Read the reasoning — that's how you learn to handicap.",
            "key_point": "Secretariat explains WHY it likes a horse. Understanding the reasoning makes you a better handicapper, not just a tip-follower.",
        },
    ],
    "golden_rules": [
        "Never bet more than you can afford to lose — treat your bankroll as tuition",
        "Stick to 2–5% of bankroll per race (a $500 bankroll = $10–25 per race)",
        "Keep records of every bet — winners AND losers. You can't improve what you don't track",
        "Favorites win ~33% of the time. Value comes from finding the OTHER 67%",
        "Understand every bet before you place it — if you can't explain why, don't bet it",
        "Never chase losses with bigger bets — that's how bankrolls disappear fast",
        "The $0.10 superfecta and $0.50 Pick 5 are the best risk/reward bets in the game",
    ],
}

_BANKROLL_GUIDE = {
    "title": "Bankroll Management for US Horse Racing Bettors",
    "intro": "How you manage your money determines whether you survive losing streaks long enough to profit. Even sharp handicappers have 5-race losing runs. Here are three proven strategies used by professional US horseplayers.",
    "strategies": [
        {
            "name": "Flat Staking",
            "summary": "Bet the same fixed dollar amount on every selection.",
            "how_it_works": "Pick a unit stake (e.g., $10 or 2% of bankroll) and never deviate. Applies to every bet regardless of confidence level.",
            "pros": ["Simple — no math required", "Limits emotional over-betting on 'sure things'", "Easy to track profit/loss in dollars"],
            "cons": ["Doesn't account for confidence level", "Misses opportunity to press when you have a clear edge"],
            "best_for": "Beginners and anyone who tends to over-bet when confident.",
            "example": "$500 bankroll → $10 flat stake. After 50 bets, you can clearly see whether you're up or down and by how much.",
        },
        {
            "name": "Percentage Staking",
            "summary": "Bet a fixed percentage of your current bankroll each time.",
            "how_it_works": "Choose 1–3% of current bankroll as your stake. As your bankroll grows, bets increase. As it shrinks, bets decrease — protecting you from ruin.",
            "pros": ["Self-adjusting protection against ruin", "Bankroll grows faster during winning streaks", "Mathematically sounder than flat staking"],
            "cons": ["Stakes shrink during losing runs", "More calculation required"],
            "best_for": "Intermediate bettors with a proven edge looking for sustainable growth.",
            "example": "$500 at 2% = $10 stake. Grow to $700 → stake becomes $14. Drop to $400 → stake becomes $8. You can never go broke chasing a single bet.",
        },
        {
            "name": "Kelly Criterion",
            "summary": "Mathematical formula that sizes bets based on your estimated edge.",
            "how_it_works": "Formula: Stake% = (b × p − q) / b, where b = (decimal odds − 1), p = estimated win probability, q = 1 − p. Only bet when Kelly gives a positive number. Most serious players use Half Kelly (divide by 2) to reduce variance.",
            "pros": ["Mathematically optimal for long-run growth", "Forces you to quantify your edge before every bet", "Prevents both overbetting and underbetting"],
            "cons": ["Requires accurate probability estimates — hard to do reliably", "Full Kelly produces large swings; Half Kelly recommended", "Over-betting destroys bankrolls fast"],
            "best_for": "Experienced players who can accurately estimate win probabilities.",
            "example": "Horse at 5/1 (6.0 decimal), you estimate 25% chance: Kelly = (5 × 0.25 − 0.75) / 5 = 10% of bankroll. Half Kelly = 5%. On a $500 bankroll, that's $25.",
        },
    ],
    "session_rules": [
        "Set a session loss limit before you start — stop for the day if you lose 20% of your bankroll",
        "Set a win target too — lock in profits before you give them back",
        "Never reload your betting account mid-session to chase losses",
        "Review your betting log weekly — look for track biases, bet type profitability, and trainer patterns you're beating",
        "The Pick 4/5/6 bets have the best long-term value — the track's takeout is offset by the pool size and carryovers",
        "If you're on tilt (frustrated, desperate), stop immediately. Come back tomorrow.",
        "A $500 bankroll at $10/race gives you 50 chances. Protect those chances.",
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
