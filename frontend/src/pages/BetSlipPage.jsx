import React from 'react';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';

function parseFractionalOdds(odds) {
  if (!odds || odds === '?') return null;
  // Handle fractional like "5/2"
  const match = String(odds).match(/^(\d+)\/(\d+)$/);
  if (match) return parseInt(match[1]) / parseInt(match[2]) + 1;
  // Handle decimal
  const dec = parseFloat(odds);
  if (!isNaN(dec) && dec > 0) return dec;
  return null;
}

function BetItem({ bet }) {
  const { removeFromBetSlip, updateStake } = useAppStore();
  const decimal = parseFractionalOdds(bet.odds);
  const payout = decimal ? (bet.stake * decimal).toFixed(2) : null;
  const profit = decimal ? (bet.stake * (decimal - 1)).toFixed(2) : null;

  return (
    <div style={{
      background: 'var(--bg-card)',
      borderRadius: 'var(--radius-md)',
      padding: '14px',
      marginBottom: 10,
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{bet.horse_name}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {bet.bet_type?.toUpperCase()} · {bet.odds}
          </div>
        </div>
        <button
          onClick={() => removeFromBetSlip(bet.horse_id, bet.bet_type)}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: 18,
            lineHeight: 1,
            padding: 4,
          }}
        >
          ×
        </button>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Stake £</span>
          <input
            type="number"
            min="1"
            value={bet.stake}
            onChange={(e) => updateStake(bet.horse_id, bet.bet_type, parseFloat(e.target.value) || 0)}
            style={{
              width: 70,
              padding: '6px 10px',
              fontSize: 14,
              fontFamily: 'var(--font-mono)',
            }}
          />
        </div>
        {payout && (
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Returns</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15, color: 'var(--accent-gold-bright)' }}>
              £{payout}
            </div>
            <div style={{ fontSize: 11, color: 'var(--accent-green-bright)' }}>
              +£{profit} profit
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function BetSlipPage() {
  const { betSlip, clearBetSlip } = useAppStore();

  const totalStake = betSlip.reduce((sum, b) => sum + (b.stake || 0), 0);

  return (
    <div>
      <PageHeader
        title="BET SLIP"
        subtitle={betSlip.length > 0 ? `${betSlip.length} selection${betSlip.length !== 1 ? 's' : ''}` : 'No selections'}
        right={
          betSlip.length > 0 ? (
            <button
              onClick={clearBetSlip}
              style={{ background: 'none', border: 'none', color: 'var(--accent-red-bright)', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
            >
              Clear all
            </button>
          ) : null
        }
      />

      <div style={{ padding: '16px' }}>
        {betSlip.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🎫</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, marginBottom: 6 }}>
              No Bets Yet
            </div>
            <div style={{ fontSize: 13 }}>
              Analyze a race and add selections to your bet slip
            </div>
          </div>
        ) : (
          <>
            {betSlip.map((bet, i) => (
              <BetItem key={`${bet.horse_id}-${bet.bet_type}-${i}`} bet={bet} />
            ))}

            <div style={{
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              border: '1px solid var(--border-medium)',
              marginTop: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Total stake</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                  £{totalStake.toFixed(2)}
                </span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
                Singles only. Each selection is an independent bet.
              </div>
              <button
                className="btn btn-primary btn-full"
                style={{ fontSize: 15 }}
                onClick={() => alert('Betting placement is for informational purposes only.')}
              >
                Place Bets · £{totalStake.toFixed(2)}
              </button>
            </div>

            <div style={{
              marginTop: 12,
              padding: '10px 14px',
              background: 'rgba(26,107,168,0.08)',
              borderRadius: 'var(--radius-md)',
              borderLeft: '2px solid var(--accent-blue)',
              fontSize: 12,
              color: 'var(--text-muted)',
            }}>
              💡 GateSmart provides betting intelligence only. Always gamble responsibly.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
