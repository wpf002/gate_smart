import { useState } from 'react';
import PageHeader from '../components/common/PageHeader';

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
    name: 'Each Way',
    emoji: '⚡',
    difficulty: 'Beginner',
    desc: 'Two bets in one: Win + Place at the same stake. Double the cost.',
    example: '$10 EW = $20 total. Win part pays full odds if 1st. Place part pays 1/4 odds if 1st, 2nd or 3rd (in a field of 8+).',
    tip: 'Popular for longshots (10/1+). The place part protects your bet if the horse runs well but doesn\'t win.',
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
    title: 'Fractional Odds (UK / Ireland)',
    emoji: '🇬🇧',
    body: `Written as 5/2, 7/4, 11/10, etc. The first number is your profit, the second is your stake.

5/2 means: stake £2, profit £5. So on a £10 bet, you profit £25 and get back £35 total.

Odds-on (like 4/6): stake £6 to profit £4. These are short-priced favourites.

Evens (1/1): stake £10, profit £10.`,
  },
  {
    title: 'Decimal Odds (Europe / Australia)',
    emoji: '🇪🇺',
    body: `Written as 3.50, 2.75, 1.80, etc. Multiply your stake by the decimal to get total return (profit + stake).

3.50 odds on a $10 bet = $35 total return ($25 profit).

Converting: fractional 5/2 → decimal = (5÷2) + 1 = 3.50

Evens = 2.00. Anything below 2.00 is odds-on.`,
  },
  {
    title: 'American (Moneyline) Odds',
    emoji: '🇺🇸',
    body: `Positive (+) odds: how much profit on a $100 bet.
+250 means $100 wins $250 profit ($350 total).

Negative (−) odds: how much you must stake to win $100 profit.
−150 means stake $150 to win $100 profit ($250 total).

Evens = +100. Short-priced favourite = −200 or lower.`,
  },
  {
    title: 'Morning Line vs. Tote Odds',
    emoji: '📊',
    body: `Morning line: estimated odds set by the track handicapper before betting opens. A guide only — not what you'll be paid.

Tote (parimutuel) odds: the live odds determined by the actual betting pool. All bets go into one pool; the track takes a cut (~17–25%) and the remainder is divided among winners.

This means: the more money bet on a horse, the shorter its odds. Value exists when a horse's true winning chance is higher than its tote price implies.`,
  },
  {
    title: 'Starting Price (SP)',
    emoji: '🏁',
    body: `The official odds at the moment a race starts, calculated from bookmaker prices in the UK/Ireland.

Taking SP means you accept whatever the final price is, rather than locking in odds early. Can be higher or lower than your early price.

For US racing, "SP" usually means the final tote odds.`,
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
    explanation: 'Reading right to left (most recent last): Won → Won → Fell 2nd → Placed 3rd → Last season break. Two recent wins is excellent form.',
  },
};

const GLOSSARY = [
  { term: 'Accumulator', def: 'Multiple selections combined into one bet — all must win for a payout. High risk, high reward.' },
  { term: 'Ante-post', def: 'Betting before the day of the race, sometimes weeks or months ahead. No refund if horse is withdrawn.' },
  { term: 'Beyer Figure', def: 'US speed figure invented by Andrew Beyer. Scale ~60–120. Standardised across all US tracks.' },
  { term: 'Box', def: 'Covering all combinations of selected horses in an exotic bet (exacta, trifecta, etc.). Increases cost but coverage.' },
  { term: 'Chalk', def: 'Slang for the race favourite (heavily bet horse).' },
  { term: 'Claiming race', def: 'Race where every horse can be purchased ("claimed") for a set price. Lowest class of race.' },
  { term: 'Closer', def: 'A horse that runs from off the pace and finishes strongly in the final furlong.' },
  { term: 'Each Way', def: 'Two bets: one on the horse to win, one on it to place (finish top 2 or 3). Costs double the stake.' },
  { term: 'Exacta', def: 'Predict 1st and 2nd in exact order.' },
  { term: 'Form', def: 'A horse\'s recent race results. "112" = won, won, 2nd (most recent last in UK notation).' },
  { term: 'Furlong', def: '1/8th of a mile = 201 metres. Race distances measured in furlongs (e.g. "6f" = 6 furlongs).' },
  { term: 'Going', def: 'Track surface condition. UK: Firm → Good to Firm → Good → Good to Soft → Soft → Heavy. Affects how horses run.' },
  { term: 'Graded stakes', def: 'Elite races graded G1 (best), G2, or G3. G1s have the biggest prize money and prestige.' },
  { term: 'Handicap', def: 'A race where horses carry different weights to equalise chances. Top-rated horse carries most weight.' },
  { term: 'Key horse', def: 'Your most confident selection, used "on top" in exotics (i.e. must finish 1st).' },
  { term: 'Lay', def: 'To bet AGAINST a horse winning (exchange betting, e.g. Betfair). You act as the bookmaker.' },
  { term: 'Longshot', def: 'A horse at high odds (10/1 or more). Low probability but high payout if it wins.' },
  { term: 'Maiden', def: 'A horse that has never won a race. Maiden races are exclusively for non-winners.' },
  { term: 'Morning line', def: 'Estimated odds set by the track handicapper before betting opens. A starting point, not final.' },
  { term: 'Overlay', def: 'A horse whose odds are higher than its true winning probability suggests. This is value.' },
  { term: 'Parimutuel', def: 'Betting system where all money goes into a pool, house takes a cut, rest paid to winners.' },
  { term: 'Post position', def: 'The starting gate stall number. Inside posts (1–3) can be advantageous on tight tracks.' },
  { term: 'Quinella', def: 'Predict 1st and 2nd in any order. Easier than exacta, lower payout.' },
  { term: 'RPR', def: 'Racing Post Rating — UK/Ireland performance rating. 130+ is elite flat, 170+ is elite jump.' },
  { term: 'Scratch', def: 'A horse withdrawn from a race after entries are taken. Check for scratches before betting.' },
  { term: 'Speed figure', def: 'Numerical rating of a horse\'s performance adjusted for track conditions. Higher = faster.' },
  { term: 'SP', def: 'Starting Price — the official odds at race time used to settle bets at SP.' },
  { term: 'Superfecta', def: 'Predict 1st through 4th in exact order. Very hard to hit, very large payouts.' },
  { term: 'Timeform', def: 'UK ratings service. Ratings measure ability; figures above 130 are top class on the flat.' },
  { term: 'Tote', def: 'The parimutuel pool betting operator. Tote odds fluctuate until the race starts.' },
  { term: 'Trifecta', def: 'Predict 1st, 2nd, and 3rd in exact order.' },
  { term: 'Underlay', def: 'A horse whose odds are lower than its true winning chance. Opposite of overlay — avoid.' },
  { term: 'Value', def: 'Exists when a horse\'s odds are higher than its true probability. Core concept of profitable betting.' },
  { term: 'Wheel', def: 'Using one horse in one leg of a multi-race bet with ALL horses in other legs.' },
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
  { id: 'bets', label: '🎰 Bet Types' },
  { id: 'odds', label: '📊 Odds' },
  { id: 'handicap', label: '🔍 Handicapping' },
  { id: 'form', label: '📋 Reading Form' },
  { id: 'bankroll', label: '💰 Bankroll' },
  { id: 'glossary', label: '📚 Glossary' },
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
        A horse's form figures show its finishing positions in recent races, most recent first (UK) or last (US). Understanding form is the first step to handicapping.
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
      {filtered.map(({ term, def }) => (
        <div key={term} style={{
          padding: '12px 0',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--accent-gold-bright)', marginBottom: 4 }}>
            {term}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{def}</div>
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
      </div>
    </div>
  );
}
