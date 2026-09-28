import { useQuery } from '@tanstack/react-query';
import { getSecretariatAccuracy, getBetCurve } from '../utils/api';
import Icon from '../components/common/Icon';

/**
 * Marketing front door for logged-out visitors.
 *
 * Every number on this page is pulled live from the same endpoints the app
 * uses, including the one that says the picks don't yet pay. Publishing that is
 * the point: it's the one claim competitors can't copy, and it can never drift
 * from what actually happened.
 *
 * It's stated as a gap to break-even over 30 days rather than as a single day's
 * loss. A day is ~130 bets, which swings 15 points on one longshot, so a daily
 * figure told a visitor whatever the dice gave. The gap is the real number and
 * it's the one worth watching: the day it turns positive, the picks pay.
 */
function Figure({ value, label, tone }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700, color: tone, lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </div>
    </div>
  );
}

export default function LandingPage({ onGetStarted }) {
  const { data: acc } = useQuery({
    queryKey: ['secretariat-accuracy'],
    queryFn: getSecretariatAccuracy,
    staleTime: 5 * 60 * 1000,
  });
  const { data: curve } = useQuery({
    queryKey: ['landing-breakeven'],
    queryFn: () => getBetCurve(30),
    staleTime: 5 * 60 * 1000,
  });

  const hasStats = acc && acc.total_predictions >= 10 && acc.win_rate_percent != null;
  const stats = [
    { label: 'Win', value: acc?.win_rate_percent },
    { label: 'Place', value: acc?.place_rate_percent },
    { label: 'Show', value: acc?.show_rate_percent },
  ];
  const be = curve?.breakeven;
  const hasGap = be && typeof be.hit_rate === 'number' && typeof be.needed_rate === 'number' && be.bets > 0;
  const clears = hasGap && be.gap > 0;

  return (
    <div style={{ minHeight: '100%', overflowY: 'auto', background: 'var(--bg-primary)' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px 64px' }}>

        {/* Hero */}
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 44, letterSpacing: '0.04em', color: 'var(--accent-gold)', lineHeight: 1 }}>
          GATESMART
        </div>
        <div style={{ fontSize: 17, color: 'var(--text-primary)', marginTop: 14, lineHeight: 1.5 }}>
          An AI handicapper that analyzes every US race, locks its picks the night before,
          and publishes exactly how it did — wins and losses.
        </div>

        {/* Live stat line */}
        {hasStats && (
          <div style={{
            display: 'flex', gap: 12, marginTop: 24, padding: '18px 20px',
            background: 'var(--bg-card)', border: '1px solid var(--border-gold)',
            borderRadius: 'var(--radius-md)',
          }}>
            {stats.map((s) => (
              <div key={s.label} style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 30, color: 'var(--accent-gold-bright)', lineHeight: 1 }}>
                  {Math.round(s.value)}%
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        )}
        {hasStats && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.6 }}>
            Secretariat's top pick over {acc.total_predictions.toLocaleString()} settled races in the
            last {acc.days ?? 30} days. Every pick is locked before post time and scored against the
            official results chart.
          </div>
        )}

        {/* The honest bit */}
        <div style={{
          marginTop: 28, padding: '16px 18px', background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 17, color: 'var(--accent-gold)', letterSpacing: '0.06em' }}>
            THE BAR WE'RE CHASING
          </div>
          {hasGap ? (
            <>
              <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                <Figure value={`${(be.hit_rate * 100).toFixed(1)}%`} label="Wins" tone="var(--accent-gold-bright)" />
                <Figure value={`${(be.needed_rate * 100).toFixed(1)}%`} label="Needs" tone="var(--text-secondary)" />
                <Figure
                  value={`${be.gap >= 0 ? '+' : '−'}${Math.abs(be.gap * 100).toFixed(1)}`}
                  label="Gap"
                  tone={clears ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)'}
                />
              </div>
              <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 12, lineHeight: 1.6 }}>
                A high win rate isn't profit. Most picks win at short prices, so the top pick has to
                win <strong>{(be.needed_rate * 100).toFixed(1)}%</strong> of the time just to return
                the stake at the prices it's actually paid. Over the last {be.days ?? 30} days it won{' '}
                <strong>{(be.hit_rate * 100).toFixed(1)}%</strong> of {be.bets.toLocaleString()} races.
                {clears
                  ? ' It clears the bar. We publish the gap every day, priced from official payoffs.'
                  : " It doesn't clear the bar yet. We publish the gap every day, priced from official payoffs, and you'll see it the day it turns."}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.6 }}>
              A high win rate isn't profit. Most picks win at short prices, so the top pick has to win
              often enough to clear what the chalk costs. We publish that gap every day, priced from
              official payoffs — good or bad.
            </div>
          )}
        </div>

        {/* How it learns */}
        <div style={{ marginTop: 32 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 17, color: 'var(--accent-gold)', letterSpacing: '0.06em', marginBottom: 12 }}>
            IT LEARNS FROM EVERY RACE
          </div>
          {[
            ['Analyzes the full card', 'Pace, class, form and market read on every US race, every day.'],
            ['Reviews its own misses', 'Each night it works through the races it got wrong and writes down the lesson.'],
            ['Applies what it learned', "Those lessons and its own hit rates feed the next day's analysis."],
          ].map(([title, body]) => (
            <div key={title} style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
              <span style={{ color: 'var(--accent-gold)', flexShrink: 0, marginTop: 2 }}>
                <Icon name="star-filled" size={14} />
              </span>
              <div>
                <div style={{ fontSize: 14, color: 'var(--text-primary)', fontWeight: 600 }}>{title}</div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55 }}>{body}</div>
              </div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <button
          onClick={onGetStarted}
          style={{
            width: '100%', marginTop: 28, padding: '14px 20px',
            background: 'var(--accent-gold)', color: '#000', border: 'none',
            borderRadius: 'var(--radius-md)', fontFamily: 'var(--font-body)',
            fontSize: 15, fontWeight: 700, cursor: 'pointer',
          }}
        >
          Get Started
        </button>

        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 20, lineHeight: 1.6, textAlign: 'center' }}>
          For US thoroughbred racing. Analysis only — not a profit guarantee.
          Bet responsibly. 18+/21+ where legal.
        </div>
      </div>
    </div>
  );
}
