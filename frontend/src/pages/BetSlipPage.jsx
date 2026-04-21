import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import AffiliateDrawer from '../components/common/AffiliateDrawer';
import { simPlaceBet, getRaceDetail } from '../utils/api';
import { trackPaperBetPlaced } from '../utils/analytics';
import Icon from '../components/common/Icon';

// Standalone helper so it can be called in the paper-trade handler
async function paperTradeBets(betSlip, qc, setTrading, setTradeResult, navigate) {
  setTrading(true);
  setTradeResult(null);
  let placed = 0;
  const errors = [];
  for (const bet of betSlip) {
    try {
      await simPlaceBet({
        race_id: bet.race_id,
        horse_id: bet.horse_id,
        horse_name: bet.horse_name,
        bet_type: bet.bet_type,
        odds: String(bet.odds),
        stake: bet.stake,
        race_name: bet.race_name || '',
        course: bet.course || '',
        jockey: bet.jockey || '',
        trainer: bet.trainer || '',
        owner: bet.owner || '',
      });
      trackPaperBetPlaced(bet.bet_type, bet.stake);
      placed++;
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Unknown error';
      errors.push(`${bet.horse_name}: ${detail}`);
    }
  }
  await qc.invalidateQueries({ queryKey: ['sim-stats'] });
  await qc.invalidateQueries({ queryKey: ['sim-bets'] });
  setTrading(false);
  if (errors.length === 0) {
    navigate('/simulator', { state: { tab: 'bets' } });
  } else if (placed > 0) {
    setTradeResult(`${placed} placed. Issues: ${errors.join(' · ')}`);
    navigate('/simulator', { state: { tab: 'bets' } });
  } else {
    setTradeResult(errors.join(' · '));
  }
}

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

function RaceStatusBar({ raceId, horseName }) {
  const { data: race } = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => getRaceDetail(raceId),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    enabled: !!raceId,
  });

  if (!race) return null;

  const status = (race.status || '').toLowerCase();
  const isFinished = ['result', 'finished', 'complete', 'completed'].includes(status) || (race.results?.length > 0);
  const isOff = !isFinished && ['off', 'active', 'in_running', 'in running'].includes(status);

  const runner = race.runners?.find(r =>
    (r.horse_name || r.horse) === horseName
  );
  const isScratched = runner && (runner.non_runner || runner.scratched ||
    ['scratched', 'non-runner', 'nr', 'withdrawn'].includes((runner.status || '').toLowerCase())
  );

  const timeStr = race.off_time || race.scheduled_time || race.time || race.race_time || '';
  let postDisplay = '';
  if (timeStr && !isFinished && !isOff) {
    try {
      postDisplay = new Date(timeStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {}
  }

  if (!isScratched && !isFinished && !isOff && !postDisplay) return null;

  return (
    <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
      {isScratched && (
        <span style={{
          fontSize: 11, fontWeight: 700,
          color: 'var(--accent-red-bright)',
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.25)',
          padding: '2px 7px', borderRadius: 4,
        }}>
          Scratched — remove from slip
        </span>
      )}
      {isFinished && (
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Race finished</span>
      )}
      {isOff && !isFinished && (
        <span style={{
          fontSize: 11, fontWeight: 700,
          color: 'var(--accent-red-bright)',
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.25)',
          padding: '2px 7px', borderRadius: 4,
        }}>
          Race Off
        </span>
      )}
      {postDisplay && (
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Post {postDisplay}</span>
      )}
    </div>
  );
}

const EXOTIC_TYPES = ['exacta', 'trifecta', 'superfecta', 'daily double', 'pick3', 'pick4', 'pick5', 'pick6'];

function BetItem({ bet }) {
  const { removeFromBetSlip, updateStake } = useAppStore();
  const navigate = useNavigate();
  const isExotic = EXOTIC_TYPES.includes((bet.bet_type || '').toLowerCase());
  const decimal = !isExotic ? parseFractionalOdds(bet.odds) : null;
  const payout = decimal ? (bet.stake * decimal).toFixed(2) : null;
  const profit = decimal ? (bet.stake * (decimal - 1)).toFixed(2) : null;

  return (
    <div style={{
      background: 'var(--bg-card)',
      borderRadius: 'var(--radius-md)',
      padding: '14px',
      marginBottom: 10,
      border: `1px solid ${isExotic ? 'rgba(201,162,39,0.2)' : 'var(--border-subtle)'}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ flex: 1, minWidth: 0, marginRight: 8 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>
            {isExotic ? (
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-gold-bright)' }}>{bet.horse_name}</span>
            ) : bet.horse_name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {bet.bet_type?.toUpperCase()}{!isExotic && bet.odds !== '?' && ` · ${bet.odds}`}
            {bet.course && <span> · {bet.course}</span>}
            {bet.race_id && (
              <button
                onClick={() => navigate(`/race/${bet.race_id}`)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-gold-dim)', fontSize: 11, padding: '0 0 0 6px' }}
              >
                → Race
              </button>
            )}
          </div>
          {(bet.jockey || bet.trainer) && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
              {[bet.jockey && `J: ${bet.jockey}`, bet.trainer && `T: ${bet.trainer}`].filter(Boolean).join(' · ')}
            </div>
          )}
          {bet.owner && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              O: {bet.owner}
            </div>
          )}
          {bet.placed_at && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Added: {new Date(bet.placed_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </div>
          )}
          <RaceStatusBar raceId={bet.race_id} horseName={bet.horse_name} />
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
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Stake $</span>
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
              ${payout}
            </div>
            <div style={{ fontSize: 11, color: 'var(--accent-green-bright)' }}>
              +${profit} profit
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function buildTellerScript(bets) {
  if (!bets.length) return '';
  const lines = bets.map((b) => {
    const stake = `$${(b.stake || 10).toFixed(2)}`;
    const type = (b.bet_type || 'win').toUpperCase();
    return `"${stake} ${type} on ${b.horse_name}${b.course ? ` in the ${b.course} race` : ''} at ${b.odds || 'SP'}."`;
  });
  return lines.join('\n');
}

function TellerScriptModal({ bets, onClose }) {
  const script = buildTellerScript(bets);
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(script).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 9000,
      padding: '24px 16px',
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-elevated)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        width: '100%',
        maxWidth: 440,
        maxHeight: '80vh',
        overflowY: 'auto',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, marginBottom: 12 }}>
          Teller Script
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.5 }}>
          Read each line aloud at the counter or window:
        </p>
        <div style={{
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          lineHeight: 1.8,
          whiteSpace: 'pre-wrap',
          marginBottom: 14,
          border: '1px solid var(--border-subtle)',
        }}>
          {script}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={copy}>
            {copied ? '✓ Copied' : 'Copy to Clipboard'}
          </button>
          <button className="btn" style={{ flex: 1, border: '1px solid var(--border-subtle)' }} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default function BetSlipPage() {
  const { betSlip, clearBetSlip, userProfile } = useAppStore();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [trading, setTrading] = useState(false);
  const [tradeResult, setTradeResult] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tellerOpen, setTellerOpen] = useState(false);

  // Deduplicate by horse_id + bet_type in case of stale persisted state
  const dedupedSlip = useMemo(() => {
    const seen = new Set();
    return betSlip.filter((b) => {
      const key = `${b.horse_id}::${b.bet_type}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [betSlip]);

  const totalStake = dedupedSlip.reduce((sum, b) => sum + (b.stake || 0), 0);

  return (
    <div>
      <PageHeader
        title="BET SLIP"
        subtitle={dedupedSlip.length > 0 ? `${dedupedSlip.length} selection${dedupedSlip.length !== 1 ? 's' : ''}` : 'No selections'}
        right={
          dedupedSlip.length > 0 ? (
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
        {dedupedSlip.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center', color: 'var(--text-muted)' }}><Icon name="picks" size={48} /></div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, marginBottom: 6 }}>
              No Bets Yet
            </div>
            <div style={{ fontSize: 13 }}>
              Analyze a race and add selections to your bet slip
            </div>
          </div>
        ) : (
          <>
            {dedupedSlip.map((bet, i) => (
              <BetItem key={`${bet.horse_id}-${bet.bet_type}-${i}`} bet={bet} />
            ))}

            {/* ── Place Bets Online ──────────────────────────────── */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-elevated) 100%)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              border: '1px solid var(--border-gold)',
              marginTop: 8,
              marginBottom: 12,
            }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--accent-gold)', marginBottom: 4 }}>
                Ready to bet? Choose where to place it:
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
                Total stake: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>${totalStake.toFixed(2)}</span>
              </div>
              <button
                className="btn btn-primary btn-full"
                style={{ fontSize: 14 }}
                onClick={() => setDrawerOpen(true)}
              >
                Bet Online — Open Sportsbook
              </button>
            </div>

            {/* ── Teller / Paper Trade ───────────────────────────── */}
            <div style={{
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              border: '1px solid var(--border-medium)',
              marginBottom: 8,
            }}>
              <button
                className="btn btn-secondary btn-full"
                style={{ fontSize: 14, marginBottom: 8 }}
                onClick={() => setTellerOpen(true)}
              >
                Bet at Counter — Teller Script
              </button>
              <button
                className="btn btn-secondary btn-full"
                style={{ fontSize: 13 }}
                disabled={trading}
                onClick={() => paperTradeBets(dedupedSlip, qc, setTrading, setTradeResult, navigate)}
              >
                {trading ? 'Placing paper bets…' : 'Paper Trade (Practice)'}
              </button>
              {tradeResult && (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--accent-red-bright)', textAlign: 'center' }}>
                  {tradeResult}
                </div>
              )}
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
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><Icon name="lightbulb" size={13} /> GateSmart provides betting intelligence only. Always gamble responsibly.</span>
            </div>
          </>
        )}
      </div>

      <AffiliateDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        region={userProfile?.region || 'usa'}
      />
      {tellerOpen && (
        <TellerScriptModal bets={dedupedSlip} onClose={() => setTellerOpen(false)} />
      )}
    </div>
  );
}
