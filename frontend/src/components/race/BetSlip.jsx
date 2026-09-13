import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRaceTicket } from '../../utils/api';
import { shareResult } from '../../utils/share';

const LABEL = { win: 'WIN', exacta: 'EXACTA', trifecta: 'TRIFECTA' };

const HOW = {
  win: 'Your horse must finish 1st.',
  exacta: 'First two, in exact order.',
  trifecta: 'First three, in exact order.',
};

const money = (n) => `$${Number(n || 0).toFixed(2)}`;

function NumberChip({ n, tone = 'neutral' }) {
  const colors = {
    neutral: { bg: 'var(--bg-secondary)', fg: 'var(--text-primary)', border: 'var(--border-medium)' },
    hit: { bg: 'rgba(46,160,67,0.18)', fg: 'var(--accent-green-bright)', border: 'var(--accent-green-bright)' },
    miss: { bg: 'var(--bg-secondary)', fg: 'var(--text-muted)', border: 'var(--border-subtle)' },
  }[tone];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      minWidth: 26, height: 26, padding: '0 6px', borderRadius: 6,
      fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
      background: colors.bg, color: colors.fg, border: `1px solid ${colors.border}`,
    }}>{n}</span>
  );
}

function Leg({ leg, settled }) {
  const tone = settled ? leg.status : 'pending';
  const bar = {
    hit: 'var(--accent-green-bright)',
    miss: 'var(--accent-red-bright)',
    unpriced: 'var(--border-medium)',
    pending: 'var(--accent-gold)',
  }[tone];

  return (
    <div className="ticket-leg" style={{ display: 'flex', gap: 12, padding: '12px 14px', '--leg-bar': bar }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--text-primary)' }}>
            {LABEL[leg.type]}
          </span>
          {!settled && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{HOW[leg.type]}</span>}
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
          {leg.numbers.map((n) => <NumberChip key={n} n={n} tone={settled && leg.status === 'hit' ? 'hit' : 'neutral'} />)}
        </div>
        {settled && leg.status === 'miss' && leg.winning_numbers && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            Came in
            {leg.winning_numbers.map((n) => <NumberChip key={n} n={n} tone="miss" />)}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right', alignSelf: 'center', minWidth: 72 }}>
        {!settled && <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-secondary)' }}>$2</div>}
        {settled && leg.status === 'hit' && (
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 700, color: 'var(--accent-green-bright)' }}>
            {money(leg.payout)}
          </div>
        )}
        {settled && leg.status === 'miss' && (
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--accent-red-bright)' }}>−$2.00</div>
        )}
        {settled && leg.status === 'unpriced' && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>No pool</div>
        )}
      </div>
    </div>
  );
}

/**
 * Secretariat's ticket for a race. Before post it shows how to bet it; after,
 * each leg turns green or red with what $2 actually paid from the official chart.
 */
export default function BetSlip({ raceId, raceFinished = false, onPlaceBet }) {
  const [shareState, setShareState] = useState('');
  const { data, isError } = useQuery({
    queryKey: ['ticket', raceId],
    queryFn: () => getRaceTicket(raceId),
    enabled: !!raceId,
    retry: false,
    // Poll for the result once the race is off, until the chart is in.
    refetchInterval: (q) => (raceFinished && !q.state.data?.settled ? 60000 : false),
  });

  if (isError || !data || !data.legs?.length) return null;
  const { legs, settled, summary } = data;
  const hits = legs.filter((l) => l.status === 'hit');

  const onShare = async () => {
    const best = [...hits].sort((a, b) => (b.payout || 0) - (a.payout || 0))[0];
    const result = await shareResult({
      title: 'GateSmart',
      text: `Secretariat hit the ${best.type} (${best.numbers.join('-')}) — $2 paid ${money(best.payout)}.`,
    });
    setShareState(result === 'copied' ? 'Copied' : result === 'shared' ? 'Shared' : '');
    if (result === 'copied') setTimeout(() => setShareState(''), 2000);
  };

  return (
    <div style={{
      marginBottom: 16, background: 'var(--bg-card)', borderRadius: 'var(--radius-md)',
      border: `1px solid ${settled && hits.length ? 'var(--accent-green-bright)' : 'var(--border-gold)'}`,
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)',
      }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)' }}>
          SECRETARIAT'S TICKET
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {settled ? 'Official result' : '$2 per bet'}
        </span>
      </div>

      <div className="ticket-legs">
        {legs.map((leg) => <Leg key={leg.type} leg={leg} settled={settled} />)}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', gap: 10 }}>
        {settled && summary ? (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-secondary)' }}>
            Bet {money(summary.staked)} · Back {money(summary.returned)} ·{' '}
            <strong style={{ color: summary.net >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)' }}>
              {summary.net >= 0 ? '+' : '−'}{money(Math.abs(summary.net))}
            </strong>
          </span>
        ) : (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Total {money(legs.length * 2)}</span>
        )}

        {settled && hits.length > 0 && (
          <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 12px' }} onClick={onShare}>
            {shareState || 'Share'}
          </button>
        )}
        {!settled && !raceFinished && onPlaceBet && (
          <button
            className="btn btn-primary"
            style={{ fontSize: 12, padding: '6px 12px' }}
            onClick={() => onPlaceBet(legs)}
          >
            Place This Bet
          </button>
        )}
      </div>
    </div>
  );
}
