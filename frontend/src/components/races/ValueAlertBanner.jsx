export default function ValueAlertBanner({ alerts, loading }) {
  if (loading) {
    return (
      <div style={{
        background: 'rgba(201,162,39,0.06)',
        border: '1px solid var(--border-gold)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 14px',
        marginBottom: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--accent-gold)',
            animation: 'pulse 1s infinite',
          }} />
          <span style={{ fontSize: 12, color: 'var(--accent-gold)' }}>Checking for value alerts…</span>
        </div>
      </div>
    );
  }

  if (!alerts || alerts.length === 0) return null;

  const levelCfg = {
    strong:   { cls: 'badge-green', label: 'STRONG VALUE' },
    moderate: { cls: 'badge-gold',  label: 'VALUE' },
    watch:    { cls: 'badge-muted', label: 'WATCH' },
  };

  return (
    <div style={{
      background: 'rgba(201,162,39,0.08)',
      border: '1px solid var(--border-gold)',
      borderRadius: 'var(--radius-md)',
      padding: '12px 14px',
      marginBottom: 12,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--accent-gold)' }}>
          ⚡ VALUE ALERTS
        </span>
        <span className="badge badge-gold">{alerts.length}</span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          Based on Secretariat's fair price estimates
        </span>
      </div>

      {/* Alert rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {alerts.map((alert) => {
          const cfg = levelCfg[alert.alert_level] || levelCfg.watch;
          return (
            <div
              key={alert.horse_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
              }}
            >
              <span style={{ fontWeight: 700, fontSize: 13, minWidth: 0 }}>{alert.horse_name}</span>
              <span className="odds-chip">{alert.current_odds}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>vs fair</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>
                {alert.fair_odds}
              </span>
              <span className={`badge ${cfg.cls}`}>{cfg.label}</span>
              <span style={{ fontSize: 12, color: 'var(--accent-green-bright)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>
                +{alert.value_percent}% overlay
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
