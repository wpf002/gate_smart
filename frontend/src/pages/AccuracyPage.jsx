import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getDailyAccuracy, getAccuracyHistory } from '../utils/api';
import PageHeader from '../components/common/PageHeader';

function WinRateDot({ rate }) {
  const pct = (rate || 0) * 100;
  const color = pct >= 50 ? 'var(--accent-green-bright)' : pct >= 35 ? 'var(--accent-gold)' : 'var(--accent-red-bright)';
  return (
    <div title={`${pct.toFixed(0)}%`} style={{
      width: 20, height: 20, borderRadius: '50%',
      background: color,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 9, fontWeight: 700, color: '#000',
      flexShrink: 0,
    }}>
      {pct.toFixed(0)}
    </div>
  );
}

export default function AccuracyPage() {
  const navigate = useNavigate();

  const { data: today, isLoading: todayLoading } = useQuery({
    queryKey: ['accuracy-daily'],
    queryFn: () => getDailyAccuracy(),
    staleTime: 5 * 60 * 1000,
  });

  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ['accuracy-history'],
    queryFn: getAccuracyHistory,
    staleTime: 5 * 60 * 1000,
  });

  const todayPending = !today || today.status === 'pending';
  const last7 = (history || []).slice(0, 7);

  return (
    <div>
      <PageHeader
        title="SECRETARIAT REPORT CARD"
        subtitle="Performance tracking across all races"
        left={
          <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 20 }}>←</button>
        }
      />

      <div style={{ padding: '16px' }}>

        {/* ── Today's stats ───────────────────────────────────────── */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(201,162,39,0.1) 0%, var(--bg-elevated) 100%)',
          border: '1px solid var(--border-gold)',
          borderRadius: 'var(--radius-lg)',
          padding: 20,
          marginBottom: 20,
        }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)', marginBottom: 12 }}>
            TODAY
          </div>

          {todayLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading…</div>
          ) : todayPending ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              ⏳ {today?.message || "Today's report generates tonight at 11 PM ET"}
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 20, marginBottom: 12, flexWrap: 'wrap' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Races called</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700 }}>{today.races_analyzed}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Win rate</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700, color: (today.win_rate || 0) >= 0.5 ? 'var(--accent-green-bright)' : 'var(--accent-gold)' }}>
                    {((today.win_rate || 0) * 100).toFixed(0)}%
                  </div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>ITM rate</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700 }}>
                    {((today.itm_rate || 0) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              {today.best_call && (
                <div style={{ fontSize: 12, color: 'var(--accent-green-bright)', marginBottom: 4 }}>
                  🎯 Best: {today.best_call}
                </div>
              )}
              {today.worst_miss && (
                <div style={{ fontSize: 12, color: 'var(--accent-red-bright)' }}>
                  ❌ Miss: {today.worst_miss}
                </div>
              )}
            </>
          )}
        </div>

        {/* ── 7-day trend ─────────────────────────────────────────── */}
        {last7.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Last 7 Days
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              {[...last7].reverse().map((r, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <WinRateDot rate={r.win_rate} />
                  <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>
                    {new Date(r.date).toLocaleDateString([], { weekday: 'short' })}
                  </span>
                </div>
              ))}
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>
                🟢 &gt;50% &nbsp; 🟡 35–50% &nbsp; 🔴 &lt;35%
              </div>
            </div>
          </div>
        )}

        {/* ── 30-day history table ─────────────────────────────────── */}
        {!histLoading && history?.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              History (Last 30 Days)
            </div>
            <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
              {/* Header */}
              <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 70px 70px', padding: '8px 12px', fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border-subtle)' }}>
                <span>Date</span>
                <span>Best Call</span>
                <span style={{ textAlign: 'right' }}>Win %</span>
                <span style={{ textAlign: 'right' }}>Races</span>
              </div>
              {history.map((r, i) => {
                const wr = (r.win_rate || 0) * 100;
                const wrColor = wr >= 50 ? 'var(--accent-green-bright)' : wr >= 35 ? 'var(--accent-gold)' : 'var(--accent-red-bright)';
                return (
                  <div key={i} style={{
                    display: 'grid', gridTemplateColumns: '100px 1fr 70px 70px',
                    padding: '9px 12px', fontSize: 12,
                    borderBottom: i < history.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                  }}>
                    <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                      {new Date(r.date).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    </span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 8 }}>
                      {r.best_call || '—'}
                    </span>
                    <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 700, color: wrColor }}>
                      {wr.toFixed(0)}%
                    </span>
                    <span style={{ textAlign: 'right', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      {r.races_analyzed}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {!histLoading && (!history || history.length === 0) && (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)', fontSize: 13 }}>
            No accuracy data yet. Reports generate nightly after races settle.
          </div>
        )}
      </div>
    </div>
  );
}
