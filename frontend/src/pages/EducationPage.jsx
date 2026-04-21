import { useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import { PARTNERS } from '../utils/affiliates';
import { trackEvent } from '../utils/analytics';

// ─── Content ──────────────────────────────────────────────────────────────────

const BET_TYPES = [
  {
    name: 'Win',
    emoji: '🥇',
    difficulty: 'Beginner',
    desc: 'Your horse must finish first. Simple, most common bet.',
    example: '$10 Win on Secretariat at 3/1 → win $30 profit + $10 back = $40 total.',
    tip: 'Best starting point for new bettors. Higher risk than Place/Show but better payouts.',
  },
  {
    name: 'Place',
    emoji: '🥈',
    difficulty: 'Beginner',
    desc: 'Your horse must finish 1st or 2nd. Lower payout, safer.',
    example: '$10 Place on Enable at 5/2 → wins if she finishes 1st or 2nd.',
    tip: 'Good for horses you like but aren\'t sure will win outright. Pays roughly 40–60% of the win price.',
  },
  {
    name: 'Show',
    emoji: '🥉',
    difficulty: 'Beginner',
    desc: 'Your horse must finish 1st, 2nd, or 3rd. Lowest payout, safest.',
    example: 'Useful in races with many runners where finishing top-3 is likely.',
    tip: 'Rarely good value — the low payout barely beats breaking even. Use sparingly.',
  },
  {
    name: 'Across the Board',
    emoji: '🎪',
    difficulty: 'Beginner',
    desc: 'Three bets in one: Win + Place + Show on the same horse. Costs 3× your base stake.',
    example: '$2 Across the Board = $6 total. Horse finishes 2nd → you collect Place and Show. Horse wins → you collect all three.',
    tip: 'Good for a horse you love but aren\'t sure will win outright. A 2nd or 3rd still pays back something.',
  },
  {
    name: 'Exacta',
    emoji: '🎯',
    difficulty: 'Intermediate',
    desc: 'Pick the 1st and 2nd place finishers in exact order.',
    example: '$2 Exacta 4-7: Horse 4 wins, Horse 7 runs second. Missed if they finish 7-4.',
    tip: 'Box it to cover both orders (costs double): "4-7 boxed exacta" covers 4-7 and 7-4.',
  },
  {
    name: 'Quinella',
    emoji: '🔄',
    difficulty: 'Intermediate',
    desc: 'Pick 1st and 2nd place in any order. Easier than exacta, lower payout.',
    example: '$5 Quinella 4-7: wins whether the finish is 4-7 or 7-4.',
    tip: 'Think of it as a pre-boxed exacta. Good when you like two horses but can\'t decide which wins.',
  },
  {
    name: 'Trifecta',
    emoji: '🏆',
    difficulty: 'Intermediate',
    desc: 'Pick 1st, 2nd, and 3rd in exact order. Big payouts.',
    example: '$1 Trifecta 4-7-2: costs $1, but box 3 horses (6 combos) = $6.',
    tip: 'Box your top 3 picks to cover all orderings. A single $1 trifecta is very hard to hit.',
  },
  {
    name: 'Superfecta',
    emoji: '💎',
    difficulty: 'Advanced',
    desc: 'Pick 1st through 4th in exact order. Lottery-level payouts.',
    example: '$0.10 Superfecta box of 4 horses (24 combos) = $2.40 total.',
    tip: 'Use $0.10 base bets and box liberally. A $1 superfecta straight is nearly impossible.',
  },
  {
    name: 'Daily Double',
    emoji: '📅',
    difficulty: 'Intermediate',
    desc: 'Pick the winner of two consecutive races.',
    example: '$2 Daily Double: Pick Race 1 winner AND Race 2 winner.',
    tip: 'Wheel one race if you have a strong opinion on one leg. E.g. horse 4 with all (ALL) in race 2.',
  },
  {
    name: 'Pick 3 / Pick 4 / Pick 5 / Pick 6',
    emoji: '🔢',
    difficulty: 'Advanced',
    desc: 'Win consecutive races. The Pick 6 (jackpot) pools can reach millions.',
    example: '$1 Pick 4 with 2×2×1×3 horses = $12 ticket.',
    tip: 'Single out one race where you have a "single" (one horse), spread in the rest. This keeps ticket cost down.',
  },
];

const ODDS_CONTENT = [
  {
    title: 'American (Moneyline) Odds',
    emoji: '🇺🇸',
    body: `The standard at US racetracks and ADW platforms like TwinSpires, TVG, NYRA Bets, and AmWager.

Positive (+) odds show profit on a $100 bet:
+250 → stake $100, profit $250 ($350 total back)
+500 → stake $100, profit $500 ($600 total back)

Negative (−) odds show how much you stake to win $100 profit:
−150 → stake $150, profit $100 ($250 total back)
−300 → stake $300, profit $100 ($400 total back)

Even money = +100. Heavy favorite might be −400 or lower.

Quick formula: +odds → profit = (odds/100) × stake. −odds → profit = (100/|odds|) × stake.`,
  },
  {
    title: 'Parimutuel / Tote Odds (How US Tracks Pay)',
    emoji: '🏦',
    body: `Almost all US racetrack wagering is parimutuel — every bet goes into a common pool.

1. All Win bets on a race go into one pool.
2. The track takes its cut (~17–25%, called the "takeout" or "vigorish").
3. Remaining money is split among winning ticket holders.

This means: the more money bet on a horse, the lower the payout. Odds change until post time.

Morning Line: the track's estimated odds before betting opens — a starting point only.
Final Tote Odds: what you actually get paid. A $2 Win ticket that pays $8.40 means +320 in American terms.

Value exists when the final tote odds are higher than the horse's true winning probability.`,
  },
  {
    title: 'Fractional Odds (UK / Ireland)',
    emoji: '🇬🇧',
    body: `Used in UK/Irish racing and sometimes shown on international simulcast feeds.

Written as 5/2, 7/4, 11/10 — first number is profit, second is stake.

5/2 on a $10 bet → profit $25, total return $35.
Evens (1/1) → stake $10, profit $10.
Odds-on like 4/6 → stake $6 to profit $4 (short favorite).

Converting to American: 5/2 → +(5÷2 × 100) = +250.
Converting to decimal: 5/2 = (5÷2) + 1 = 3.50.`,
  },
  {
    title: 'Decimal Odds (Europe / Australia)',
    emoji: '🌍',
    body: `Common on international betting exchanges and European books.

Written as 3.50, 2.75, 1.80 — multiply stake × decimal for total return.

3.50 × $10 = $35 total ($25 profit).
Evens = 2.00. Anything below 2.00 is odds-on (favorite).

Converting: fractional 5/2 → decimal = (5÷2) + 1 = 3.50.
American +250 → decimal = (250÷100) + 1 = 3.50.`,
  },
  {
    title: 'Overlay vs. Underlay (Finding Value)',
    emoji: '💡',
    body: `The core concept of profitable betting:

Overlay: horse's actual winning chance is HIGHER than odds imply. BET IT.
Example: odds suggest 20% chance (4/1), but you think it wins 30%. That's value.

Underlay: horse's actual winning chance is LOWER than odds imply. SKIP IT.
Example: favorite at −200 (67% implied), but it only wins 50% of the time.

Implied probability from American odds:
+odds: 100 / (odds + 100)    →   +250 = 100/350 = 28.6%
−odds: |odds| / (|odds| + 100)  →  −200 = 200/300 = 66.7%

Bet horses where your estimate beats the implied probability. That's an edge.`,
  },
];

const HANDICAPPING = [
  {
    title: 'Speed Figures',
    icon: '⚡',
    body: `A numerical rating of how fast a horse ran, adjusted for track variant (how fast or slow the track was playing that day). The most common are:

• Beyer Speed Figures (US): scale ~60–120. A 100+ Beyer is top-class.
• Timeform ratings (UK): similar concept, 135+ is elite.
• Racing Post Rating (RPR): UK/Ireland equivalent.

Key insight: compare figures run at the same class level. A 95 Beyer at a claiming race does not equal a 95 Beyer in a stakes race.`,
  },
  {
    title: 'Pace Analysis',
    icon: '🏃',
    body: `Races are won and lost in fractions. Identify:

• Early pace (E): horses that want to lead from the gate
• Presser (P): sits just off the leader
• Sustained pace (S): closes from off the pace
• Deep closer (C): comes from far back

Front-runners struggle when there are multiple E types (contested pace). Closers struggle on tracks with a strong rail bias or in short races.

Look at the half-mile fraction: if it's suicidally fast (under 45 seconds for 4f), closers will likely sweep by late.`,
  },
  {
    title: 'Class',
    icon: '🎖️',
    body: `Every race has a class level. From lowest to highest (US):

Maiden → Claiming → Allowance → Stakes → Graded Stakes (G3 → G2 → G1)

A horse dropping in class (e.g. from Allowance to Claiming) is often a sign the trainer is trying to find a spot to win. Can be a positive.

A horse rising sharply in class (maiden winner moving to G1) is taking a big risk. Needs standout figures to succeed.`,
  },
  {
    title: 'Trainer & Jockey Stats',
    icon: '👨‍🏫',
    body: `Trainers have patterns:
• Win % with first-time starters
• Win % after layoffs (30–60 days off, 60+ days off)
• Win % when dropping in class
• Turf specialist vs. dirt specialist

Jockey angles:
• Win % at the specific track
• Win % for this trainer (trainer-jockey combo win %)
• Some jockeys excel at closing; others are aggressive early

Resources like Equibase (US), Timeform (UK), or Racing Post show these stats.`,
  },
  {
    title: 'Track Bias',
    icon: '🛤️',
    body: `Track bias = a systematic advantage for horses in certain positions or running styles on a given day.

Common biases:
• Rail bias (inside post advantage): rail is fast/dead
• Speed bias: front-runners winning wire-to-wire all day
• Deep closer bias: horses coming from off the pace sweeping by

Causes: recent rain, rail movement, surface maintenance, temperature.

How to spot it: watch the first 2–3 races. If every winner comes from the inside post, that's a bias. Bet WITH the bias.`,
  },
  {
    title: 'Form Cycles & Layoffs',
    icon: '📈',
    body: `Horses run in cycles. Key patterns:

• Horse off a big win: sometimes backs up (had a hard race)
• Horse improving: 3rd → 2nd → ready to win
• Horse returning from 60+ days off: fitness question, but trainers often target a specific spot
• "Bounce" pattern: horse runs a career-best, then disappoints next time (peaked)

Layoff angles: some trainers have high win% with horses fresh off 90+ days. Check trainer stats. A horse working fast in the mornings before a comeback is a good sign.`,
  },
];

const BANKROLL = [
  {
    title: 'Flat Betting',
    rec: 'Recommended for beginners',
    color: 'var(--accent-green)',
    body: `Bet the same amount every race — e.g. 2% of bankroll (called 1 unit).

$500 bankroll → $10 per bet.

Simple, disciplined, prevents chasing losses. You'll still profit if you find value consistently.`,
  },
  {
    title: 'Unit Sizing',
    rec: 'Most popular among professionals',
    color: 'var(--accent-gold)',
    body: `Scale bet size based on your confidence:
• 1 unit (2% of bankroll): standard bet
• 2 units: high confidence
• 3 units: maximum — rarely used

Never go above 5% of bankroll on a single bet. Variance in horse racing is extreme — even the best handicappers hit 35% win rate at best.`,
  },
  {
    title: 'Kelly Criterion',
    rec: 'For experienced bettors only',
    color: 'var(--accent-blue)',
    body: `A mathematical formula for optimal bet sizing based on edge:

Bet % = (bp − q) / b

Where: b = decimal odds − 1, p = your estimated win probability, q = 1 − p

Example: horse at 4/1 (b=4), you think it wins 30% (p=0.30, q=0.70):
Kelly % = (4×0.30 − 0.70) / 4 = 0.20/4 = 5%

Use "fractional Kelly" (half Kelly = 2.5%) to reduce variance. Full Kelly risks massive drawdowns.`,
  },
  {
    title: 'Session Rules',
    rec: 'Discipline saves bankrolls',
    color: 'var(--accent-red)',
    body: `Set hard rules before you start:
• Stop-loss: if you lose 25% of session bankroll, stop for the day
• Win goal: optional, but locking in a big day prevents giving it back
• Never chase: doubling up after a loss is the fastest way to go broke
• One race at a time: don't have 6 bets running simultaneously
• Bet with your head, not your heart — never bet on sentiment`,
  },
];

const FORM_GUIDE = {
  figures: [
    { symbol: '1', meaning: 'Won' },
    { symbol: '2', meaning: '2nd place' },
    { symbol: '3', meaning: '3rd place' },
    { symbol: '4–9', meaning: '4th–9th place' },
    { symbol: '0', meaning: 'Finished outside top 9' },
    { symbol: 'F', meaning: 'Fell' },
    { symbol: 'U', meaning: 'Unseated rider' },
    { symbol: 'P', meaning: 'Pulled up' },
    { symbol: 'R', meaning: 'Refused' },
    { symbol: 'B', meaning: 'Brought down' },
    { symbol: 'S', meaning: 'Slipped up' },
    { symbol: 'D', meaning: 'Disqualified' },
    { symbol: 'C', meaning: 'Carried out' },
    { symbol: '-', meaning: 'Season break (between years)' },
    { symbol: '/', meaning: 'Previous season separator' },
  ],
  example: {
    form: '3-1-2F-11',
    explanation: 'Reading left to right (oldest → newest): 3rd → Won → 2nd → Fell → Won → Won. Two consecutive wins to end the sequence — excellent current form.',
  },
};

const GLOSSARY = [
  // ── Bet Types ──────────────────────────────────────────────────────────────
  { term: 'Win', plain_english: 'Your horse has to cross the finish line first. You get paid; otherwise you lose your stake.', def: 'Bet on a horse to finish 1st. The simplest and most common bet. Best starting point for new bettors.' },
  { term: 'Place', plain_english: 'Your horse has to finish 1st or 2nd. Safer than Win, but pays less.', def: 'Bet on a horse to finish 1st or 2nd. Lower payout than Win, but safer.' },
  { term: 'Show', plain_english: 'Your horse has to finish in the top 3. Very safe, but the payout is often barely more than your stake.', def: 'Bet on a horse to finish 1st, 2nd, or 3rd. Lowest payout of the straight bets. Use sparingly — value is often poor.' },
  { term: 'Across the Board', plain_english: 'You bet Win + Place + Show all at once. You still get something back even if your horse only finishes 3rd.', def: 'Three bets in one: Win + Place + Show on the same horse. Costs 3× base stake. Pays something even for a 3rd-place finish.' },
  { term: 'Exacta', plain_english: 'Pick who comes 1st AND who comes 2nd — in the right order. Hard to hit but pays much more than a Win bet.', def: 'Predict the 1st and 2nd place finishers in exact order. Box it to cover both orderings (costs double).' },
  { term: 'Quinella', plain_english: 'Pick who comes 1st and 2nd in ANY order — easier than an Exacta but pays less.', def: 'Predict 1st and 2nd in any order — a pre-boxed exacta. Easier to hit, lower payout.' },
  { term: 'Trifecta', plain_english: 'Pick 1st, 2nd, AND 3rd in the right order. Big payouts. "Box" your picks so any order counts.', def: 'Predict 1st, 2nd, and 3rd in exact order. Huge payouts. Box 3+ horses to cover all orderings.' },
  { term: 'Superfecta', plain_english: 'Pick the top 4 finishers in exact order. Very hard but can pay thousands. Use 10-cent bets and box many horses.', def: 'Predict 1st through 4th in exact order. Use $0.10 base bets and box liberally — very hard to hit straight.' },
  { term: 'Daily Double', def: 'Pick the winner of two consecutive designated races. Wheel one leg if confident in the other.' },
  { term: 'Pick 3', def: 'Pick winners of 3 consecutive races. A great medium-risk multi-race bet to build up.' },
  { term: 'Pick 4', def: 'Pick winners of 4 consecutive races. Single out one leg where you have a strong opinion to keep cost down.' },
  { term: 'Pick 5', def: 'Pick winners of 5 consecutive races. Jackpot pools often carry over — can be enormous.' },
  { term: 'Pick 6', def: 'Pick winners of 6 consecutive races. The marquee jackpot bet at US tracks. Pool can reach millions when it carries over.' },
  { term: 'Box', def: 'Cover all combinations of selected horses in an exotic bet (exacta box, trifecta box, etc.). Increases cost but increases coverage.' },
  { term: 'Key horse', def: 'Your most confident selection, used "on top" in exotics — it must finish 1st. Spread other horses in the remaining positions.' },
  { term: 'Wheel', def: 'Using one horse in a specific leg with ALL (or many) horses in another leg. E.g. Key horse 4 with ALL in leg 2.' },
  { term: 'Part-wheel', def: 'Like a wheel, but selecting only a subset of horses in the other legs. Balances cost and coverage.' },
  // ── Race Types ─────────────────────────────────────────────────────────────
  { term: 'Maiden race', def: 'Open only to horses that have never won a race. Maidens are learning — form is less reliable.' },
  { term: 'Maiden Special Weight (MSW)', def: 'Highest-quality maiden race, all horses carry equal weight. Often features well-bred debut runners from top stables.' },
  { term: 'Claiming race', def: 'Every horse entered can be purchased ("claimed") for the listed price. Lowest class of race. Trainer dropping a horse sharply in claiming price is often targeting a win.' },
  { term: 'Allowance race', def: 'Mid-level race above claiming. Horses earn weight allowances based on past wins. Competitive fields without the claiming risk.' },
  { term: 'Optional Claiming', def: 'Horses can be entered at a claiming price or optionally at allowance conditions. Offers flexibility and tends to draw strong fields.' },
  { term: 'Stakes race', def: 'Premium races where owners pay entry/nomination fees. Better horses, bigger purses. Listed, G3, G2, G1 in ascending prestige.' },
  { term: 'Graded Stakes (G1 / G2 / G3)', def: 'Elite races graded by quality. G1 is the top (Kentucky Derby, Breeders\' Cup). G2 and G3 are highly competitive. Winning a grade defines a horse\'s career.' },
  { term: 'Handicap race', def: 'Horses carry different weights assigned by the racing secretary to equalize chances. Top-rated horse carries the most. Common in UK/Ireland.' },
  { term: 'Turf race', def: 'Run on a grass course. Separate from dirt racing. Some horses specialize on turf — check past turf form specifically.' },
  { term: 'Synthetic / All-Weather', def: 'Artificial surface (Polytrack, Tapeta, Cushion Track) that rides differently from dirt. Form on synthetic doesn\'t always transfer to dirt and vice versa.' },
  // ── Speed & Form ───────────────────────────────────────────────────────────
  { term: 'Beyer Speed Figure', plain_english: 'A number that grades how fast a horse ran, adjusted for track conditions. Higher = faster. Compare it to the other horses in today\'s race.', def: 'US speed rating invented by Andrew Beyer, published in Daily Racing Form. Scale ~40–120. Adjusted for track speed (variant). A 100+ Beyer is elite. Compare figures run at similar class levels.' },
  { term: 'Equibase Speed Figure', def: 'Official speed figure compiled by Equibase (JCSA). Comparable concept to Beyer — higher is faster, adjusted for track variant.' },
  { term: 'TimeForm Rating', def: 'UK/Ireland performance rating. 130+ is top class on the flat, 170+ is elite over jumps. Also used internationally.' },
  { term: 'RPR (Racing Post Rating)', def: 'UK/Ireland rating comparable to TimeForm. 130+ flat, 170+ jumps is elite level.' },
  { term: 'Form string', def: 'A horse\'s sequence of finishing positions. In UK/US notation, read left to right: oldest run first, most recent run last. "3121" = 3rd, 1st, 2nd, 1st (most recent).' },
  { term: 'Workout', def: 'A timed training run (breeze) at the track before a race. Fast workouts indicate fitness. "4f in :46" means 4 furlongs in 46 seconds. Bullet workouts (fastest of the day) are highlighted in bold.' },
  { term: 'Bounce', def: 'A horse that runs a career-best effort and then disappoints next time. The theory: peak performance takes a toll. Risky to back a horse off a big effort.' },
  // ── Pace ──────────────────────────────────────────────────────────────────
  { term: 'Front-runner (E)', def: 'A horse that immediately goes to the front and leads from the gate. Struggles if several other speed horses force a contested early pace.' },
  { term: 'Presser (P)', def: 'Sits just off the leader in 2nd–4th early. Well-positioned to take over if the front-runner falters.' },
  { term: 'Stalker (S)', def: 'Runs in the middle of the pack, just off the pace. Flexible — can push forward or wait for a late run.' },
  { term: 'Closer (C)', def: 'Comes from the back of the field and relies on a big late kick. Needs a hot pace up front to set it up. Struggles in slow-pace, wire-to-wire races.' },
  { term: 'Lone speed', def: 'A front-runner with no other natural speed horses in the race. Huge advantage — can control pace and dictate terms. A key angle.' },
  { term: 'Contested pace', def: 'Multiple front-runners fighting for the early lead. Sets fast early fractions, which typically benefits closers.' },
  { term: 'Pace scenario', def: 'The expected shape of a race based on the running styles of the field. Knowing the pace scenario helps predict which horses will be advantaged or disadvantaged.' },
  // ── Track & Conditions ────────────────────────────────────────────────────
  { term: 'Fast (track condition)', def: 'Optimal dirt condition — dry and firm. Most speed figures are earned on fast tracks. Best for front-runners.' },
  { term: 'Sloppy', def: 'Wet dirt after rain — puddles on surface but base is firm. Some horses love slop ("mudlarks"). Check past sloppy form.' },
  { term: 'Muddy', def: 'Wet and soft throughout. Heavier going than sloppy. Biases toward horses with past mud form.' },
  { term: 'Sealed', def: 'Track surface has been packed down when wet. More predictable than muddy. Labeled "sealed" in past performances.' },
  { term: 'Good (turf)', def: 'Standard turf condition — not too firm, not too soft. Most turf horses handle good going.' },
  { term: 'Firm (turf)', def: 'Hard, dry turf. Fast ground. Some horses prefer firm, others struggle.' },
  { term: 'Yielding / Soft / Heavy (turf)', def: 'Increasingly wet turf conditions. Heavy = very soft and tiring. Horses with breeding for soft ground (e.g. certain European bloodlines) are favored.' },
  { term: 'Track bias', plain_english: 'Some days, horses on a specific part of the track (e.g. the inside lane) consistently win. If you notice a pattern in the first few races, bet horses that run in that zone.', def: 'A systematic advantage for horses in certain positions or running styles on a given day (e.g. rail advantage, speed bias). Watch early races to identify it, then bet WITH the bias.' },
  { term: 'Rail', def: 'The inside barrier of the track. Rail position can be a big advantage (rail bias) or disadvantage (dead rail). Check how the inside has been running.' },
  { term: 'Post position', def: 'The starting gate stall number (1 = inside rail). Inside posts (1–3) can be advantageous on tight turns. Outside posts (8+) force wider paths.' },
  { term: 'Furlong', def: '1/8th of a mile = 201 meters. US race distances are measured in furlongs. A 6-furlong race is 6/8 = 0.75 miles. A 1-mile race = 8 furlongs.' },
  // ── Class & Ratings ───────────────────────────────────────────────────────
  { term: 'Class', def: 'The quality level of a horse and the races it competes in. US class ladder (low to high): Maiden → Claiming → Allowance → Stakes → G3 → G2 → G1.' },
  { term: 'Class drop', def: 'A horse entered in a lower class race than its recent starts. Trainer targeting a spot to win. Often a strong betting angle.' },
  { term: 'Class rise', def: 'Stepping up significantly in class — e.g. first graded stakes after allowance wins. Needs outstanding figures to be competitive. Risky bet.' },
  { term: 'Claiming price', def: 'The price at which a horse in a claiming race can be purchased by another licensed trainer. A horse in a $25,000 claiming race can be claimed for $25,000.' },
  // ── Odds & Value ──────────────────────────────────────────────────────────
  { term: 'Morning line', def: 'Estimated odds set by the track handicapper before betting opens. A guide only — final tote odds depend on public money.' },
  { term: 'Overlay', plain_english: 'The horse is priced higher than it should be — you\'re getting more money than the risk deserves. This is where profit comes from.', def: 'A horse whose tote odds are higher than its true winning probability. This is value — the core concept of profitable betting.' },
  { term: 'Underlay', plain_english: 'The horse is priced too low — everyone loves it, so the payout is poor relative to the actual risk. Skip it.', def: 'A horse whose tote odds are lower than its true winning chance. Overbacked by the public. Avoid — negative expected value.' },
  { term: 'Parimutuel', plain_english: 'All bets go into one pool, the track takes a cut, and the rest is divided among the winners. Your payout depends on how much others bet on the same horse.', def: 'Betting system where all money on a bet type pools together. Track takes a cut (~17–25%), the rest is paid to winners. Standard at US racetracks.' },
  { term: 'Takeout', def: 'The percentage the track keeps from each wagering pool (house edge). Typically 15–25% depending on bet type. Exactas/trifectas have higher takeout than Win.' },
  { term: 'Chalk', def: 'Slang for the race favorite — the horse with the most money bet on it.' },
  { term: 'Longshot', def: 'A horse at long odds (+1000 or higher). Very low win probability but massive payout if it hits.' },
  { term: 'Implied probability', def: 'The win percentage implied by a horse\'s odds. +300 = 25% chance. −200 = 67% chance. If your estimate is higher than implied, it\'s an overlay.' },
  { term: 'Scratch', def: 'A horse withdrawn from a race after entries close. Check for scratches before placing tickets — pools are recalculated.' },
  // ── Trainer & Jockey ──────────────────────────────────────────────────────
  { term: 'Trainer win %', def: 'Percentage of races a trainer wins. Key stats: win % with first-time starters, win % after layoffs, win % when dropping in class. Available on Equibase.' },
  { term: 'Trainer-jockey combo', def: 'The win percentage when a specific trainer and jockey work together. A high-percentage combo is a meaningful angle.' },
  { term: 'First-time starter (debut)', def: 'A horse racing for the first time. No public form to evaluate — rely on workouts, trainer stats, and breeding.' },
  { term: 'Claim angle', def: 'When a trainer claims a horse and runs it in a new race shortly after. If the trainer has a strong post-claim win %, pay attention.' },
  // ── Equipment ─────────────────────────────────────────────────────────────
  { term: 'Blinkers', def: 'Cups attached to a horse\'s hood that restrict its vision, helping it focus. "First time blinkers" often produces improvement — a known betting angle.' },
  { term: 'Lasix (Furosemide)', def: 'A diuretic given to racehorses to prevent exercise-induced pulmonary hemorrhage (bleeding). Most US horses race on Lasix. "First time Lasix" is often a positive angle.' },
  { term: 'Tongue tie', def: 'A strap securing the horse\'s tongue to prevent it being swallowed during racing. Can improve breathing.' },
  { term: 'Mud caulks', def: 'Special horseshoes with spikes for traction in muddy/sloppy conditions. A horse equipped with mud caulks on a wet track has a grip advantage.' },
  // ── Results & Terms ───────────────────────────────────────────────────────
  { term: 'Maiden', def: 'A horse that has never won a race. Once it wins, it "breaks its maiden."' },
  { term: 'Photo finish', def: 'When horses finish too close to determine a winner by eye. Stewards review a high-speed photograph. Result is held until the photo is examined.' },
  { term: 'Disqualification (DQ)', def: 'A horse is placed behind another due to interference during the race. Stewards make the call — can affect payout.' },
  { term: 'Stewards\' inquiry', def: 'Officials reviewing the race for potential interference. Bets are settled after the inquiry is resolved.' },
  { term: 'Dead heat', def: 'Two (or more) horses finish simultaneously and share the placing. Winnings are split proportionally between tied tickets.' },
  { term: 'Pulled up (P)', def: 'A horse stopped during a race by its jockey, usually due to injury or distress. Form shows as "P" in the string.' },
  { term: 'Fell (F)', def: 'Horse fell during the race (usually in jump racing). Shown as "F" in form.' },
  { term: 'Refused (R)', def: 'Horse refused to jump an obstacle or start from the gate. Shown as "R" in form.' },
  { term: 'Season break ( - / )', def: 'Separator in form string between racing seasons or years. "-" or "/" between figures. Ignore distant past form if the horse\'s current yard/trainer changed.' },
  { term: 'Accumulator / Parlay', def: 'Multiple selections combined into one bet — all must win for a payout. High risk, high reward. Each winner rolls the profit into the next leg.' },
  { term: 'Ante-post betting', def: 'Betting weeks or months before the race (e.g. Kentucky Derby futures). No refund if horse is withdrawn. Higher odds, but risk of non-runner.' },
  { term: 'Equibase', def: 'The official data provider for US thoroughbred racing. Past performances, workouts, speed figures, and stats all sourced from Equibase (equibase.com).' },
  { term: 'Daily Racing Form (DRF)', def: 'The bible of US horse racing — provides comprehensive past performances, Beyer figures, trainer/jockey stats, and handicapping tools (drf.com).' },
  { term: 'ADW (Advance Deposit Wagering)', def: 'Online platforms where you can bet North American racing from your account. Major ADWs include TwinSpires, NYRA Bets, TVG, and AmWager.' },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return (
    <div style={{
      fontFamily: 'var(--font-display)',
      fontSize: 11,
      letterSpacing: '0.12em',
      color: 'var(--text-muted)',
      textTransform: 'uppercase',
      marginBottom: 12,
      marginTop: 4,
    }}>
      {children}
    </div>
  );
}

function BetTypeCard({ bet }) {
  const [open, setOpen] = useState(false);
  const diffColor = bet.difficulty === 'Beginner'
    ? 'var(--accent-green-bright)'
    : bet.difficulty === 'Intermediate'
      ? 'var(--accent-gold-bright)'
      : 'var(--accent-red-bright)';

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: `1px solid ${open ? 'var(--border-gold)' : 'var(--border-subtle)'}`,
        borderRadius: 'var(--radius-md)',
        marginBottom: 8,
        overflow: 'hidden',
        transition: 'border-color 0.15s',
      }}
    >
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 16px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
        }}
      >
        <span style={{ fontSize: 22, lineHeight: 1 }}>{bet.emoji}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)' }}>{bet.name}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{bet.desc}</div>
        </div>
        <span style={{ fontSize: 10, fontWeight: 700, color: diffColor, flexShrink: 0 }}>
          {bet.difficulty}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 4 }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{
            marginTop: 12,
            padding: '10px 14px',
            background: 'rgba(201,162,39,0.06)',
            borderRadius: 8,
            borderLeft: '2px solid var(--accent-gold-dim)',
            fontSize: 13,
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
            fontFamily: 'var(--font-mono)',
          }}>
            📌 {bet.example}
          </div>
          <div style={{
            marginTop: 10,
            padding: '8px 12px',
            background: 'rgba(26,107,168,0.08)',
            borderRadius: 8,
            borderLeft: '2px solid var(--accent-blue)',
            fontSize: 12,
            color: 'var(--text-secondary)',
            lineHeight: 1.5,
          }}>
            💡 {bet.tip}
          </div>
        </div>
      )}
    </div>
  );
}

function AccordionCard({ title, emoji, body, color }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `1px solid ${open ? (color ? color + '44' : 'var(--border-gold)') : 'var(--border-subtle)'}`,
      borderRadius: 'var(--radius-md)',
      marginBottom: 8,
      overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 16px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
        }}
      >
        {emoji && <span style={{ fontSize: 20 }}>{emoji}</span>}
        <span style={{ flex: 1, fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>{title}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{
          padding: '0 16px 16px',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: 13,
          color: 'var(--text-secondary)',
          lineHeight: 1.8,
          whiteSpace: 'pre-line',
        }}>
          <div style={{ marginTop: 12 }}>{body}</div>
        </div>
      )}
    </div>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'bets',     label: 'Bet Types'     },
  { id: 'odds',     label: 'Odds'          },
  { id: 'handicap', label: 'Handicapping'  },
  { id: 'form',     label: 'Reading Form'  },
  { id: 'bankroll', label: 'Bankroll'      },
  { id: 'glossary', label: 'Glossary'      },
];

// ─── Tab content ──────────────────────────────────────────────────────────────

function BetsTab() {
  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
        Horse racing offers more bet types than almost any other sport. Start with Win bets, then graduate to exotics as you gain confidence.
      </p>
      <SectionLabel>Straight Bets (single horse)</SectionLabel>
      {BET_TYPES.slice(0, 4).map(b => <BetTypeCard key={b.name} bet={b} />)}
      <SectionLabel style={{ marginTop: 16 }}>Exotic Bets (multiple horses)</SectionLabel>
      {BET_TYPES.slice(4, 8).map(b => <BetTypeCard key={b.name} bet={b} />)}
      <SectionLabel>Multi-Race Bets</SectionLabel>
      {BET_TYPES.slice(8).map(b => <BetTypeCard key={b.name} bet={b} />)}
    </div>
  );
}

function OddsTab() {
  return (
    <div>
      <div style={{
        background: 'rgba(201,162,39,0.08)',
        border: '1px solid var(--border-gold)',
        borderRadius: 'var(--radius-md)',
        padding: '12px 16px',
        marginBottom: 16,
        fontSize: 13,
        color: 'var(--text-secondary)',
        lineHeight: 1.6,
      }}>
        🧠 <strong style={{ color: 'var(--accent-gold-bright)' }}>The Golden Rule:</strong> Odds represent implied probability. 3/1 (4.00 decimal) implies 25% win chance. If YOU think the horse wins 35% of the time, that's VALUE — bet it. If you think it wins 15%, it's overpriced — skip it.
      </div>
      {ODDS_CONTENT.map(o => <AccordionCard key={o.title} title={o.title} emoji={o.emoji} body={o.body} />)}
      <div style={{ marginTop: 20 }}>
        <SectionLabel>Quick Conversion Reference</SectionLabel>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['Fractional', 'Decimal', 'American', 'Implied %'].map(h => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['1/5', '1.20', '−500', '83%'],
                ['1/2', '1.50', '−200', '67%'],
                ['Evens', '2.00', '+100', '50%'],
                ['6/4', '2.50', '+150', '40%'],
                ['2/1', '3.00', '+200', '33%'],
                ['5/2', '3.50', '+250', '29%'],
                ['3/1', '4.00', '+300', '25%'],
                ['4/1', '5.00', '+400', '20%'],
                ['9/2', '5.50', '+450', '18%'],
                ['5/1', '6.00', '+500', '17%'],
                ['10/1', '11.00', '+1000', '9%'],
                ['20/1', '21.00', '+2000', '5%'],
              ].map(row => (
                <tr key={row[0]} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {row.map((cell, i) => (
                    <td key={i} style={{
                      padding: '8px 10px',
                      fontFamily: i < 3 ? 'var(--font-mono)' : 'var(--font-body)',
                      color: i === 3 ? 'var(--text-muted)' : 'var(--text-primary)',
                      fontSize: 12,
                    }}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function HandicapTab() {
  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
        Handicapping is the art of evaluating horses to find winners — and more importantly, <em>value</em>. Even beginners can improve immediately by focusing on 2–3 key factors.
      </p>
      {HANDICAPPING.map(h => <AccordionCard key={h.title} title={h.title} emoji={h.icon} body={h.body} />)}
      <div style={{
        marginTop: 20, padding: '14px 16px',
        background: 'rgba(42,122,75,0.08)',
        border: '1px solid rgba(42,122,75,0.25)',
        borderRadius: 'var(--radius-md)',
        fontSize: 13,
        color: 'var(--text-secondary)',
        lineHeight: 1.6,
      }}>
        🎯 <strong style={{ color: 'var(--accent-green-bright)' }}>Beginner priority order:</strong> Focus first on (1) recent form, (2) class level, (3) distance suitability. Speed figures and pace come later. Don't try to master everything at once.
      </div>
    </div>
  );
}

function FormTab() {
  const [showAll, setShowAll] = useState(false);
  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
        A horse's form figures show its finishing positions in recent races. Always read left to right: oldest run first, most recent run last. "3121" = 3rd, 1st, 2nd, 1st — the 1st on the right is what it did most recently.
      </p>

      <div style={{ marginBottom: 20 }}>
        <SectionLabel>Example Form String</SectionLabel>
        <div style={{
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-md)',
          padding: '16px',
          border: '1px solid var(--border-subtle)',
        }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 28, color: 'var(--accent-gold-bright)', marginBottom: 10, letterSpacing: 4 }}>
            {FORM_GUIDE.example.form}
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {FORM_GUIDE.example.explanation}
          </p>
        </div>
      </div>

      <SectionLabel>Form Figure Reference</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: 0 }}>
        {(showAll ? FORM_GUIDE.figures : FORM_GUIDE.figures.slice(0, 7)).map(({ symbol, meaning }) => (
          <div key={symbol} style={{ display: 'contents' }}>
            <div style={{
              padding: '8px 12px',
              borderBottom: '1px solid var(--border-subtle)',
              fontFamily: 'var(--font-mono)',
              fontSize: 16,
              fontWeight: 700,
              color: 'var(--accent-gold-bright)',
            }}>{symbol}</div>
            <div style={{
              padding: '8px 12px',
              borderBottom: '1px solid var(--border-subtle)',
              fontSize: 13,
              color: 'var(--text-secondary)',
              display: 'flex', alignItems: 'center',
            }}>{meaning}</div>
          </div>
        ))}
      </div>
      {!showAll && (
        <button
          onClick={() => setShowAll(true)}
          style={{
            marginTop: 8, fontSize: 12, color: 'var(--accent-gold)',
            background: 'none', border: 'none', cursor: 'pointer',
          }}
        >
          Show all symbols ▼
        </button>
      )}

      <div style={{ marginTop: 24 }}>
        <SectionLabel>What to Look For</SectionLabel>
        {[
          { icon: '✅', label: 'Improving run', desc: 'Form reads ...3-2-1 — horse is getting better. Strong signal.' },
          { icon: '⚠️', label: 'Class drop', desc: 'Ran in G1, now in Allowance. Trainer looking for easier spot — often wins.' },
          { icon: '🔴', label: 'Bounce risk', desc: 'Career-best last time. May have peaked. Tread carefully.' },
          { icon: '✅', label: 'Freshened up', desc: 'Long break but trainer has strong record with returning horses.' },
          { icon: '⚠️', label: 'Lots of zeros', desc: 'Consistently failing to place. Unless big drop in class, avoid.' },
        ].map(({ icon, label, desc }) => (
          <div key={label} style={{
            display: 'flex', gap: 12, marginBottom: 10,
            background: 'var(--bg-card)',
            borderRadius: 8, padding: '10px 14px',
            border: '1px solid var(--border-subtle)',
          }}>
            <span style={{ fontSize: 18, flexShrink: 0 }}>{icon}</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2 }}>{label}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BankrollTab() {
  return (
    <div>
      <div style={{
        background: 'rgba(192,57,43,0.08)',
        border: '1px solid rgba(192,57,43,0.2)',
        borderRadius: 'var(--radius-md)',
        padding: '12px 16px',
        marginBottom: 20,
        fontSize: 13,
        lineHeight: 1.6,
        color: 'var(--text-secondary)',
      }}>
        ⚠️ <strong style={{ color: 'var(--accent-red-bright)' }}>Rule #1:</strong> Only bet what you can afford to lose. Set a dedicated betting bankroll separate from living expenses. Never chase losses.
      </div>
      {BANKROLL.map(b => (
        <div key={b.title} style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderLeft: `3px solid ${b.color}`,
          borderRadius: 'var(--radius-md)',
          padding: '16px',
          marginBottom: 12,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>{b.title}</div>
            <span style={{ fontSize: 11, color: b.color, fontWeight: 600 }}>{b.rec}</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-line' }}>{b.body}</p>
        </div>
      ))}
      <div style={{
        marginTop: 8, padding: '14px 16px',
        background: 'rgba(201,162,39,0.06)',
        border: '1px solid var(--border-gold)',
        borderRadius: 'var(--radius-md)',
        fontSize: 13,
        color: 'var(--text-secondary)',
        lineHeight: 1.6,
      }}>
        💡 <strong style={{ color: 'var(--accent-gold-bright)' }}>Reality check:</strong> Even professional handicappers hit ~30–35% win rate on flat bets. A 50-bet losing streak is statistically possible. Size bets so a bad run doesn't wipe you out.
      </div>
    </div>
  );
}

function GlossaryTab() {
  const [search, setSearch] = useState('');
  const filtered = GLOSSARY.filter(g =>
    g.term.toLowerCase().includes(search.toLowerCase()) ||
    g.def.toLowerCase().includes(search.toLowerCase())
  );
  return (
    <div>
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search terms…"
        style={{ width: '100%', padding: '10px 14px', marginBottom: 16, fontSize: 14 }}
      />
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
        {filtered.length} terms
      </div>
      {filtered.map(({ term, def, plain_english }) => (
        <div key={term} style={{
          padding: '12px 0',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--accent-gold-bright)', marginBottom: plain_english ? 3 : 4 }}>
            {term}
          </div>
          {plain_english && (
            <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 4 }}>
              {plain_english}
            </div>
          )}
          <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>{def}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function EducationPage() {
  const [activeTab, setActiveTab] = useState('bets');

  return (
    <div>
      <PageHeader title="LEARN" subtitle="Master horse racing from zero to pro" />

      {/* Tab bar */}
      <div style={{
        display: 'flex',
        overflowX: 'auto',
        borderBottom: '1px solid var(--border-subtle)',
        scrollbarWidth: 'none',
      }}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            style={{
              flexShrink: 0,
              padding: '10px 16px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === id ? '2px solid var(--accent-gold)' : '2px solid transparent',
              color: activeTab === id ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              whiteSpace: 'nowrap',
              transition: 'color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div style={{ padding: '20px 20px' }}>
        {activeTab === 'bets' && <BetsTab />}
        {activeTab === 'odds' && <OddsTab />}
        {activeTab === 'handicap' && <HandicapTab />}
        {activeTab === 'form' && <FormTab />}
        {activeTab === 'bankroll' && <BankrollTab />}
        {activeTab === 'glossary' && <GlossaryTab />}

        {/* ── TAKE IT FURTHER ─────────────────────────────────────── */}
        <div style={{ marginTop: 40, paddingTop: 24, borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontSize: 11,
            letterSpacing: '0.12em',
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
            marginBottom: 16,
          }}>
            Take It Further
          </div>

          {/* West Point Thoroughbreds card */}
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-gold)',
            borderRadius: 'var(--radius-md)',
            padding: '20px',
          }}>
            <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--text-primary)', marginBottom: 12 }}>
              🏆 Own a Piece of a Racehorse
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 16 }}>
              Understanding racing is one thing. Owning a share of a thoroughbred is another level entirely.
              West Point Thoroughbreds is the gold standard in racing partnerships — they've produced major
              stakes winners and their partners get paddock access, winner's circle moments, and true
              insider experience.
            </p>
            <button
              onClick={() => {
                trackEvent('partner_click', { partner: 'westpoint' });
                window.open(PARTNERS.westpoint.url, '_blank', 'noopener,noreferrer');
              }}
              style={{
                background: 'var(--accent-gold)',
                color: '#000',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                padding: '10px 20px',
                fontSize: 13,
                fontWeight: 700,
                cursor: 'pointer',
                width: '100%',
              }}
            >
              {PARTNERS.westpoint.cta} →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
