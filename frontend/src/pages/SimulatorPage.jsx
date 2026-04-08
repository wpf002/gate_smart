import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import PageHeader from '../components/common/PageHeader';
import { simGetBets, simGetStats, simTopup, simReset, simSettle, simDeleteBet } from '../utils/api';

const TOPUP_AMOUNTS = [50, 100, 200, 500];

function BankTab({ stats, onTopup, onReset, topping, resetting, topupError }) {
  const bank = stats?.bank ?? 500;
  const netPnl = stats?.net_pnl ?? 0;
  const pnlColor = netPnl >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)';

  return (
    <div style={{ padding: '0 16px 16px' }}>
      {/* Bank card */}
      <div style={{
        background: 'var(--bg-elevated)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        textAlign: 'center',
        border: '1px solid var(--border-medium)',
        marginBottom: 16,
      }}>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
          Paper Bank
        </div>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 42, fontWeight: 700, color: 'var(--accent-gold-bright)', lineHeight: 1 }}>
          £{bank.toFixed(2)}
        </div>
        {stats?.total_wagered > 0 && (
          <div style={{ marginTop: 10, fontSize: 14, color: pnlColor, fontFamily: 'var(--font-mono)' }}>
            {netPnl >= 0 ? '+' : ''}£{netPnl.toFixed(2)} net P&L
          </div>
        )}
      </div>

      {/* Topup */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Top up bank
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {TOPUP_AMOUNTS.map((amt) => (
            <button
              key={amt}
              className="btn btn-secondary"
              disabled={topping}
              onClick={() => onTopup(amt)}
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              +£{amt}
            </button>
          ))}
        </div>
      </div>

      {topupError && (
        <div style={{
          padding: '8px 12px',
          background: 'rgba(239,68,68,0.1)',
          borderRadius: 'var(--radius-md)',
          borderLeft: '2px solid var(--accent-red-bright)',
          fontSize: 12,
          color: 'var(--accent-red-bright)',
          marginBottom: 12,
        }}>
          {topupError}
        </div>
      )}

      {/* Disclaimer */}
      <div style={{
        padding: '10px 14px',
        background: 'rgba(26,107,168,0.08)',
        borderRadius: 'var(--radius-md)',
        borderLeft: '2px solid var(--accent-blue)',
        fontSize: 12,
        color: 'var(--text-muted)',
        marginBottom: 16,
        lineHeight: 1.5,
      }}>
        Paper trading simulator — no real money involved.<br />
        <span style={{ opacity: 0.8 }}>Your <strong>Profile Bankroll</strong> is a separate value used by Secretariat for stake sizing recommendations.</span>
      </div>

      {/* Reset */}
      <button
        className="btn"
        disabled={resetting}
        onClick={onReset}
        style={{
          width: '100%',
          fontSize: 13,
          color: 'var(--accent-red-bright)',
          border: '1px solid var(--accent-red-dim)',
          background: 'transparent',
        }}
      >
        {resetting ? 'Resetting…' : 'Reset Simulator'}
      </button>
    </div>
  );
}

function BetStatusBadge({ status }) {
  const cfg = {
    pending: { bg: 'rgba(212,175,55,0.12)', color: 'var(--accent-gold-bright)', label: 'Pending' },
    won:     { bg: 'rgba(34,197,94,0.12)',  color: 'var(--accent-green-bright)', label: 'Won' },
    lost:    { bg: 'rgba(239,68,68,0.12)',  color: 'var(--accent-red-bright)',   label: 'Lost' },
    void:    { bg: 'rgba(107,114,128,0.12)', color: 'var(--text-muted)',         label: 'Void' },
  }[status] || { bg: 'transparent', color: 'var(--text-muted)', label: status };

  return (
    <span style={{
      fontSize: 11,
      fontWeight: 700,
      padding: '2px 7px',
      borderRadius: 4,
      background: cfg.bg,
      color: cfg.color,
    }}>
      {cfg.label}
    </span>
  );
}

function BetCard({ bet, onSettle, settling, settleMsg, onDelete, deleting }) {
  const isPending = bet.status === 'pending';
  const pnlColor = bet.pnl >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)';
  const isThisSettling = settling === bet.race_id;
  const isDeleting = deleting === bet.bet_id;

  return (
    <div style={{
      background: 'var(--bg-card)',
      borderRadius: 'var(--radius-md)',
      padding: '12px 14px',
      border: '1px solid var(--border-subtle)',
      marginBottom: 10,
      opacity: isDeleting ? 0.5 : 1,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <div style={{ flex: 1, minWidth: 0, marginRight: 8 }}>
          <div style={{ fontWeight: 700, fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {bet.horse_name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {bet.bet_type?.toUpperCase()} · {bet.odds}
            {bet.course && <span> · {bet.course}</span>}
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
              {new Date(bet.placed_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <BetStatusBadge status={bet.status} />
          <button
            onClick={() => onDelete(bet.bet_id)}
            disabled={isDeleting}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
              padding: '2px 4px',
            }}
            title="Remove bet"
          >
            ×
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
        <div>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Stake </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700 }}>£{bet.stake.toFixed(2)}</span>
          {!isPending && (
            <>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 4px' }}>→</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: pnlColor }}>
                £{bet.returns.toFixed(2)}
              </span>
            </>
          )}
        </div>
        {isPending && (
          <button
            className="btn btn-secondary"
            disabled={isThisSettling}
            onClick={() => onSettle(bet.race_id)}
            style={{ fontSize: 11, padding: '4px 10px' }}
          >
            {isThisSettling ? 'Checking…' : 'Check Result'}
          </button>
        )}
        {!isPending && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: pnlColor, fontWeight: 700 }}>
            {bet.pnl >= 0 ? '+' : ''}£{bet.pnl.toFixed(2)}
          </span>
        )}
      </div>
      {!isThisSettling && settleMsg?.raceId === bet.race_id && (
        <div style={{
          marginTop: 8,
          fontSize: 12,
          color: 'var(--text-secondary)',
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 'var(--radius-sm)',
          padding: '6px 8px',
        }}>
          {settleMsg.text}
        </div>
      )}
    </div>
  );
}

function BetsTab({ bets, onSettle, settling, settleMsg, onReset, resetting, onDelete, deleting }) {
  if (!bets || bets.length === 0) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, marginBottom: 6 }}>No bets yet</div>
        <div style={{ fontSize: 13 }}>
          Add horses to your bet slip and paper trade them
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '0 16px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
        <button
          disabled={resetting}
          onClick={onReset}
          style={{
            fontSize: 12,
            fontWeight: 600,
            padding: '4px 10px',
            borderRadius: 6,
            border: '1px solid var(--accent-red-dim)',
            background: 'transparent',
            color: 'var(--accent-red-bright)',
            cursor: 'pointer',
          }}
        >
          {resetting ? 'Clearing…' : 'Clear All'}
        </button>
      </div>
      {bets.map((bet) => (
        <BetCard key={bet.bet_id} bet={bet} onSettle={onSettle} settling={settling} settleMsg={settleMsg} onDelete={onDelete} deleting={deleting} />
      ))}
    </div>
  );
}

function StatRow({ label, value, mono, color }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '10px 0',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{
        fontSize: 14,
        fontWeight: 700,
        fontFamily: mono ? 'var(--font-mono)' : undefined,
        color: color || 'inherit',
      }}>
        {value}
      </span>
    </div>
  );
}

function StatsTab({ stats }) {
  if (!stats || stats.total_bets === 0) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, marginBottom: 6 }}>No stats yet</div>
        <div style={{ fontSize: 13 }}>Place some paper bets to see your P&L</div>
      </div>
    );
  }

  const winRate = stats.settled_bets > 0
    ? ((stats.won_bets / stats.settled_bets) * 100).toFixed(1)
    : '—';
  const pnlColor = stats.net_pnl >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)';
  const roiColor = stats.roi >= 0 ? 'var(--accent-green-bright)' : 'var(--accent-red-bright)';

  return (
    <div style={{ padding: '0 16px 16px' }}>
      {/* Summary card */}
      <div style={{
        background: 'var(--bg-elevated)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px',
        textAlign: 'center',
        border: '1px solid var(--border-medium)',
        marginBottom: 16,
      }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
          Net P&L
        </div>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 36, fontWeight: 700, color: pnlColor }}>
          {stats.net_pnl >= 0 ? '+' : ''}£{stats.net_pnl.toFixed(2)}
        </div>
        <div style={{ fontSize: 13, color: roiColor, fontFamily: 'var(--font-mono)', marginTop: 4 }}>
          ROI {stats.roi >= 0 ? '+' : ''}{stats.roi}%
        </div>
      </div>

      <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', padding: '0 14px', border: '1px solid var(--border-subtle)' }}>
        <StatRow label="Total bets" value={stats.total_bets} />
        <StatRow label="Pending" value={stats.pending_bets} />
        <StatRow label="Won" value={stats.won_bets} color="var(--accent-green-bright)" />
        <StatRow label="Lost" value={stats.lost_bets} color="var(--accent-red-bright)" />
        <StatRow label="Win rate" value={winRate !== '—' ? `${winRate}%` : '—'} />
        <StatRow label="Total wagered" value={`£${stats.total_wagered.toFixed(2)}`} mono />
        <StatRow label="Total returns" value={`£${stats.total_returns.toFixed(2)}`} mono />
      </div>
    </div>
  );
}

export default function SimulatorPage() {
  const [tab, setTab] = useState('bank');
  const [settling, setSettling] = useState(null);
  const [settleMsg, setSettleMsg] = useState(null);
  const qc = useQueryClient();

  const { data: statsData } = useQuery({
    queryKey: ['sim-stats'],
    queryFn: simGetStats,
    refetchInterval: 30000,
    refetchOnMount: 'always',
    staleTime: 0,
  });

  const { data: betsData } = useQuery({
    queryKey: ['sim-bets'],
    queryFn: simGetBets,
    refetchInterval: 30000,
    refetchOnMount: 'always',
    staleTime: 0,
  });

  const topupMutation = useMutation({
    mutationFn: simTopup,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sim-stats'] }),
  });

  const topupError = topupMutation.isError
    ? (topupMutation.error?.response?.data?.detail || 'Top-up failed — is the backend running?')
    : null;

  const resetMutation = useMutation({
    mutationFn: simReset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sim-stats'] });
      qc.invalidateQueries({ queryKey: ['sim-bets'] });
    },
  });

  const [deleting, setDeleting] = useState(null);
  const handleDelete = useCallback(async (betId) => {
    setDeleting(betId);
    try {
      await simDeleteBet(betId);
      qc.invalidateQueries({ queryKey: ['sim-bets'] });
      qc.invalidateQueries({ queryKey: ['sim-stats'] });
    } catch {
      // silent — bet stays visible
    } finally {
      setDeleting(null);
    }
  }, [qc]);

  const handleSettle = useCallback(async (raceId) => {
    setSettling(raceId);
    setSettleMsg(null);
    try {
      const result = await simSettle(raceId);
      qc.invalidateQueries({ queryKey: ['sim-bets'] });
      qc.invalidateQueries({ queryKey: ['sim-stats'] });
      const count = result?.settled?.length ?? 0;
      setSettleMsg({
        raceId,
        text: count > 0
          ? `${count} bet${count !== 1 ? 's' : ''} settled`
          : 'Results not available yet — check back after the race',
      });
    } catch {
      setSettleMsg({ raceId, text: 'Could not fetch results — try again later' });
    } finally {
      setSettling(null);
    }
  }, [qc]);

  const handleReset = useCallback(async () => {
    if (!window.confirm('Reset simulator? All bets and P&L will be cleared.')) return;
    resetMutation.mutate();
  }, [resetMutation]);

  const stats = statsData;
  const bets = betsData?.bets || [];

  const TABS = [
    { id: 'bank',  label: 'Bank' },
    { id: 'bets',  label: `Bets${bets.length > 0 ? ` (${bets.length})` : ''}` },
    { id: 'stats', label: 'Stats' },
  ];

  return (
    <div>
      <PageHeader
        title="SIMULATOR"
        subtitle="Paper trading · no real money"
      />

      {/* Tab bar */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '0 16px',
        marginBottom: 16,
        gap: 4,
      }}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              flex: 1,
              padding: '10px 0',
              background: 'none',
              border: 'none',
              borderBottom: tab === id ? '2px solid var(--accent-gold)' : '2px solid transparent',
              color: tab === id ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              marginBottom: -1,
              transition: 'color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'bank' && (
        <BankTab
          stats={stats}
          onTopup={(amt) => topupMutation.mutate(amt)}
          onReset={handleReset}
          topping={topupMutation.isPending}
          resetting={resetMutation.isPending}
          topupError={topupError}
        />
      )}
      {tab === 'bets' && (
        <BetsTab
          bets={bets}
          onSettle={handleSettle}
          settling={settling}
          settleMsg={settleMsg}
          onReset={handleReset}
          resetting={resetMutation.isPending}
          onDelete={handleDelete}
          deleting={deleting}
        />
      )}
      {tab === 'stats' && (
        <StatsTab stats={stats} />
      )}
    </div>
  );
}
