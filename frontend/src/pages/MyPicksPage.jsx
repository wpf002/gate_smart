import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../store';
import PageHeader from '../components/common/PageHeader';
import AffiliateDrawer from '../components/common/AffiliateDrawer';
import { simGetBets, getRaceDetail } from '../utils/api';
import Icon from '../components/common/Icon';

// ─── Helpers ────────────────────────────────────────────────────────────────

function parseFractionalOdds(odds) {
  if (!odds || odds === '?') return null;
  const match = String(odds).match(/^(\d+)\/(\d+)$/);
  if (match) return parseInt(match[1]) / parseInt(match[2]) + 1;
  const dec = parseFloat(odds);
  if (!isNaN(dec) && dec > 0) return dec;
  return null;
}

function buildCounterScript(picks) {
  if (!picks.length) return '';
  return picks
    .map((b) => {
      const stake = `$${(b.stake || 10).toFixed(2)}`;
      const type = (b.bet_type || 'win').toUpperCase();
      return `"${stake} ${type} on ${b.horse_name}${b.course ? ` in the ${b.course} race` : ''} at ${b.odds || 'SP'}."`;
    })
    .join('\n');
}

// ─── Race status badge for a pick ───────────────────────────────────────────

function RaceStatusBadge({ raceId, horseName }) {
  const { data: race } = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => getRaceDetail(raceId),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    enabled: !!raceId,
  });

  if (!race) return null;

  const status = (race.status || '').toLowerCase();
  const isFinished = ['result', 'finished', 'complete', 'completed'].includes(status) || race.results?.length > 0;
  const isOff = !isFinished && ['off', 'active', 'in_running', 'in running'].includes(status);
  const runner = race.runners?.find((r) => (r.horse_name || r.horse) === horseName);
  const isScratched = runner && (runner.non_runner || runner.scratched ||
    ['scratched', 'non-runner', 'nr', 'withdrawn'].includes((runner.status || '').toLowerCase()));

  const timeStr = race.off_time || race.scheduled_time || race.time || race.race_time || '';
  let postDisplay = '';
  if (timeStr && !isFinished && !isOff) {
    try { postDisplay = new Date(timeStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch {}
  }

  if (!isScratched && !isFinished && !isOff && !postDisplay) return null;

  return (
    <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {isScratched && (
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-red-bright)', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', padding: '2px 7px', borderRadius: 4 }}>
          Scratched
        </span>
      )}
      {isFinished && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Race finished</span>}
      {isOff && !isFinished && (
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-red-bright)', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', padding: '2px 7px', borderRadius: 4 }}>
          Race Off
        </span>
      )}
      {postDisplay && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Post {postDisplay}</span>}
    </div>
  );
}

// ─── Individual pick card ────────────────────────────────────────────────────

const EXOTIC_TYPES = ['exacta', 'trifecta', 'superfecta', 'daily double', 'pick3', 'pick4', 'pick5', 'pick6'];

function PickCard({ pick }) {
  const { removeFromBetSlip, updateStake } = useAppStore();
  const navigate = useNavigate();
  const isExotic = EXOTIC_TYPES.includes((pick.bet_type || '').toLowerCase());
  const decimal = !isExotic ? parseFractionalOdds(pick.odds) : null;
  const payout = decimal ? (pick.stake * decimal).toFixed(2) : null;
  const profit = decimal ? (pick.stake * (decimal - 1)).toFixed(2) : null;

  return (
    <div style={{
      background: 'var(--bg-card)',
      borderRadius: 'var(--radius-md)',
      padding: '14px',
      marginBottom: 10,
      border: `1px solid ${isExotic ? 'rgba(201,162,39,0.2)' : 'var(--border-subtle)'}`,
    }}>
      {/* Horse + remove */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ flex: 1, minWidth: 0, marginRight: 8 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>
            {isExotic
              ? <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-gold-bright)' }}>{pick.horse_name}</span>
              : pick.horse_name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {pick.bet_type?.toUpperCase()}{!isExotic && pick.odds !== '?' && ` · ${pick.odds}`}
            {pick.course && <span> · {pick.course}</span>}
            {pick.race_id && (
              <button
                onClick={() => navigate(`/race/${pick.race_id}`)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-gold-dim)', fontSize: 11, padding: '0 0 0 6px' }}
              >
                → Race
              </button>
            )}
          </div>
          {(pick.jockey || pick.trainer) && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
              {[pick.jockey && `J: ${pick.jockey}`, pick.trainer && `T: ${pick.trainer}`].filter(Boolean).join(' · ')}
            </div>
          )}
          <RaceStatusBadge raceId={pick.race_id} horseName={pick.horse_name} />
        </div>
        <button
          onClick={() => removeFromBetSlip(pick.horse_id, pick.bet_type)}
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 20, lineHeight: 1, padding: 4 }}
        >
          ×
        </button>
      </div>

      {/* Stake + payout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>If I bet $</span>
          <input
            type="number"
            min="1"
            value={pick.stake}
            onChange={(e) => updateStake(pick.horse_id, pick.bet_type, parseFloat(e.target.value) || 0)}
            style={{ width: 70, padding: '6px 10px', fontSize: 14, fontFamily: 'var(--font-mono)' }}
          />
        </div>
        {payout ? (
          <div style={{ flex: 1, textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Could return</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--accent-gold-bright)', fontWeight: 700 }}>
              ${payout}
            </div>
            <div style={{ fontSize: 11, color: 'var(--accent-green-bright)' }}>+${profit} profit</div>
          </div>
        ) : (
          <div style={{ flex: 1, textAlign: 'right', fontSize: 12, color: 'var(--text-muted)' }}>
            Payout depends on pool
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Counter script modal ────────────────────────────────────────────────────

function CounterScriptModal({ picks, onClose }) {
  const script = buildCounterScript(picks);
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(script).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9000, padding: '24px 16px' }}
      onClick={onClose}
    >
      <div
        style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-lg)', padding: '24px', width: '100%', maxWidth: 440, maxHeight: '80vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,0.6)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, marginBottom: 8 }}>Counter Script</div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.5 }}>
          Read each line aloud at the betting window:
        </p>
        <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', padding: '14px', fontFamily: 'var(--font-mono)', fontSize: 13, lineHeight: 1.8, whiteSpace: 'pre-wrap', marginBottom: 14, border: '1px solid var(--border-subtle)' }}>
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

// ─── Past picks (history) ────────────────────────────────────────────────────

function BetStatusBadge({ status }) {
  const cfg = {
    pending: { bg: 'rgba(212,175,55,0.12)', color: 'var(--accent-gold-bright)', label: 'Pending' },
    won:     { bg: 'rgba(34,197,94,0.12)',  color: 'var(--accent-green-bright)', label: 'Won' },
    lost:    { bg: 'rgba(239,68,68,0.12)',  color: 'var(--accent-red-bright)',   label: 'Lost' },
    void:    { bg: 'rgba(107,114,128,0.12)', color: 'var(--text-muted)',         label: 'Void' },
  }[status] || { bg: 'transparent', color: 'var(--text-muted)', label: status };

  return (
    <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: cfg.bg, color: cfg.color }}>
      {cfg.label}
    </span>
  );
}

function PastPicksSection() {
  const [open, setOpen] = useState(false);
  const { data: betsData, isLoading } = useQuery({
    queryKey: ['sim-bets'],
    queryFn: simGetBets,
    staleTime: 30000,
    enabled: open,
  });

  const bets = useMemo(() => betsData?.bets || [], [betsData]);

  return (
    <div style={{ marginTop: 20 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '12px 14px',
          cursor: 'pointer',
          color: 'var(--text-primary)',
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        <span>Past tracked picks</span>
        <span style={{ fontSize: 16, color: 'var(--text-muted)', transition: 'transform 0.2s', display: 'inline-block', transform: open ? 'rotate(180deg)' : 'none' }}>
          ▾
        </span>
      </button>

      {open && (
        <div style={{ marginTop: 8 }}>
          {isLoading && (
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: 13 }}>
              Loading…
            </div>
          )}
          {!isLoading && bets.length === 0 && (
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: 13 }}>
              No past picks yet — add horses from race pages.
            </div>
          )}
          {bets.map((bet) => {
            const pnlColor = (bet.pnl || 0) >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)';
            return (
              <div
                key={bet.bet_id}
                style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', padding: '12px 14px', border: '1px solid var(--border-subtle)', marginBottom: 8 }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, minWidth: 0, marginRight: 8 }}>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{bet.horse_name}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                      {bet.bet_type?.toUpperCase()} · {bet.odds}{bet.course && ` · ${bet.course}`}
                    </div>
                    {bet.placed_at && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                        {new Date(bet.placed_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </div>
                    )}
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <BetStatusBadge status={bet.status} />
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, marginTop: 4 }}>
                      ${bet.stake?.toFixed(2)}
                      {bet.status !== 'pending' && (
                        <span style={{ color: pnlColor, marginLeft: 6 }}>
                          → {bet.pnl >= 0 ? '+' : ''}${bet.pnl?.toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function MyPicksPage() {
  const { betSlip, clearBetSlip, userProfile } = useAppStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [scriptOpen, setScriptOpen] = useState(false);

  const picks = useMemo(() => {
    const seen = new Set();
    return betSlip.filter((b) => {
      const key = `${b.horse_id}::${b.bet_type}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [betSlip]);

  const totalStake = picks.reduce((sum, b) => sum + (b.stake || 0), 0);

  return (
    <div>
      <PageHeader
        title="MY PICKS"
        subtitle={picks.length > 0 ? `${picks.length} selection${picks.length !== 1 ? 's' : ''}` : 'No picks yet'}
        right={
          picks.length > 0 ? (
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
        {picks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center', color: 'var(--text-muted)' }}><Icon name="races" size={48} /></div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, marginBottom: 6 }}>
              No Picks Yet
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.6 }}>
              Browse races, find a horse you like, and tap <strong>Add to Picks</strong> to see what your bet could return.
            </div>
          </div>
        ) : (
          <>
            {/* ── How to place this bet ─────────────────────────── */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-elevated) 100%)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              border: '1px solid var(--border-gold)',
              marginBottom: 16,
            }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--accent-gold)', marginBottom: 4 }}>
                Ready to place these?
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
                Total stake if all placed:{' '}
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
                  ${totalStake.toFixed(2)}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, fontSize: 13 }}
                  onClick={() => setDrawerOpen(true)}
                >
                  Bet Online
                </button>
                <button
                  className="btn btn-secondary"
                  style={{ flex: 1, fontSize: 13 }}
                  onClick={() => setScriptOpen(true)}
                >
                  Bet at Counter
                </button>
              </div>
            </div>

            {/* ── Pick cards ────────────────────────────────────── */}
            {picks.map((pick, i) => (
              <PickCard key={`${pick.horse_id}-${pick.bet_type}-${i}`} pick={pick} />
            ))}
          </>
        )}

        {/* ── Past picks (always accessible) ────────────────────── */}
        <PastPicksSection />

        <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(26,107,168,0.08)', borderRadius: 'var(--radius-md)', borderLeft: '2px solid var(--accent-blue)', fontSize: 12, color: 'var(--text-muted)' }}>
          GateSmart shows potential returns only. Always gamble responsibly.
        </div>
      </div>

      <AffiliateDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        region={userProfile?.region || 'usa'}
      />
      {scriptOpen && (
        <CounterScriptModal picks={picks} onClose={() => setScriptOpen(false)} />
      )}
    </div>
  );
}
