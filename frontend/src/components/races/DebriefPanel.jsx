import Icon from '../common/Icon';

export default function DebriefPanel({ debrief, loading }) {
  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--accent-gold)',
            animation: 'pulse 1s infinite',
            flexShrink: 0,
          }} />
          <span style={{ fontSize: 13, color: 'var(--accent-gold)' }}>
            Pulling official chart…
          </span>
        </div>
        {[75, 55, 40].map((w, i) => (
          <div key={i} className="skeleton" style={{ height: 12, width: `${w}%`, borderRadius: 4, marginBottom: 10 }} />
        ))}
      </div>
    );
  }

  if (!debrief) return null;

  const accuracyCfg = {
    hit:     { cls: 'badge-green', label: '✓ TOP PICK WON' },
    miss:    { cls: 'badge-red',   label: '✗ TOP PICK OFF THE BOARD' },
    partial: { cls: 'badge-gold',  label: '~ TOP PICK ITM' },
  };
  const accBadge = debrief.prediction_check?.outcome
    ? accuracyCfg[debrief.prediction_check.outcome]
    : null;

  const Section = ({ label, children }) => (
    <div style={{ marginBottom: 18 }}>
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 12,
        color: 'var(--text-muted)',
        letterSpacing: '0.08em',
        marginBottom: 8,
      }}>
        {label}
      </div>
      {children}
    </div>
  );

  const cellStyle = {
    padding: '6px 8px',
    fontSize: 12,
    color: 'var(--text-secondary)',
    borderBottom: '1px solid var(--border-subtle)',
  };
  const headStyle = {
    ...cellStyle,
    fontFamily: 'var(--font-display)',
    fontSize: 11,
    color: 'var(--text-muted)',
    letterSpacing: '0.06em',
    textAlign: 'left',
  };
  const numStyle = { ...cellStyle, fontFamily: 'var(--font-mono)', textAlign: 'right' };

  const posColor = (pos) => {
    const n = parseInt(pos);
    if (n === 1) return '#FFD700';
    if (n === 2) return '#C0C0C0';
    if (n === 3) return '#CD7F32';
    return 'var(--text-muted)';
  };

  // Canonical display order for exotic wagers. Anything unrecognised falls to
  // the end so unusual track-specific wagers still render, just last.
  const wagerRank = (wager) => {
    if (!wager) return 999;
    const w = String(wager).toLowerCase().trim();
    if (w.includes('exacta')) return 1;
    if (w.includes('trifecta')) return 2;
    if (w.includes('superfecta')) return 3;
    if (w.includes('exact 5') || w.includes('exact five') || w.includes('super high') || w.includes('high 5') || w.includes('high five') || w.includes('hi-5') || w.includes('pentafecta')) return 4;
    if (w.includes('daily double') || w === 'dd') return 5;
    if (w.includes('pick 3') || w.includes('pick three')) return 6;
    if (w.includes('pick 4') || w.includes('pick four')) return 7;
    if (w.includes('pick 5') || w.includes('pick five')) return 8;
    return 999;
  };

  const race = debrief.race || {};
  const sortedExotics = debrief.exotics
    ? [...debrief.exotics].sort((a, b) => wagerRank(a.wager) - wagerRank(b.wager))
    : [];

  return (
    <div style={{ padding: '0 0 8px' }}>
      <div style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-gold)',
        borderRadius: 'var(--radius-md)',
        padding: 14,
        marginBottom: 16,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--accent-gold)' }}>
            OFFICIAL RESULT
          </span>
          {accBadge && (
            <span className={`badge ${accBadge.cls}`}>{accBadge.label}</span>
          )}
        </div>
        {race.purse && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', letterSpacing: '0.04em', marginBottom: 16 }}>
            OPTIONAL CLAIMING VALUE: <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{race.purse}</span>
          </div>
        )}

      {/* Official order */}
      {debrief.official_order?.length > 0 && (
        <Section label="OFFICIAL ORDER">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ ...headStyle, width: 32 }}>POS</th>
                <th style={{ ...headStyle, width: 40 }}>#</th>
                <th style={headStyle}>HORSE</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>WIN</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>PLACE</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>SHOW</th>
              </tr>
            </thead>
            <tbody>
              {debrief.official_order.map((r, i) => (
                <tr key={i}>
                  <td style={{ ...cellStyle, color: posColor(r.position), fontWeight: 700 }}>{r.position}</td>
                  <td style={{ ...cellStyle, fontFamily: 'var(--font-mono)' }}>{r.number}</td>
                  <td style={cellStyle}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{r.horse}</div>
                    {(r.jockey || r.trainer) && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {[r.jockey, r.trainer].filter(Boolean).join(' · ')}
                      </div>
                    )}
                  </td>
                  <td style={r.win_payoff   ? { ...numStyle, color: 'var(--accent-gold-bright)', fontWeight: 600 } : numStyle}>{r.win_payoff   || '—'}</td>
                  <td style={r.place_payoff ? { ...numStyle, color: 'var(--accent-gold-bright)', fontWeight: 600 } : numStyle}>{r.place_payoff || '—'}</td>
                  <td style={r.show_payoff  ? { ...numStyle, color: 'var(--accent-gold-bright)', fontWeight: 600 } : numStyle}>{r.show_payoff  || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {/* Pace fractions */}
      {debrief.fractions?.length > 0 && (
        <Section label={`PACE${debrief.winning_time ? ` · WINNING TIME ${debrief.winning_time}` : ''}`}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={headStyle}>CALL</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>SPLIT</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>CUMULATIVE</th>
              </tr>
            </thead>
            <tbody>
              {debrief.fractions.map((f, i) => (
                <tr key={i}>
                  <td style={cellStyle}>{f.call}</td>
                  <td style={numStyle}>{f.split}</td>
                  <td style={numStyle}>{f.cumulative}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {/* Exotic payoffs */}
      {sortedExotics.length > 0 && (
        <Section label="EXOTIC PAYOFFS">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={headStyle}>WAGER</th>
                <th style={headStyle}>NUMBERS</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>BASE</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>PAYOFF</th>
                <th style={{ ...headStyle, textAlign: 'right' }}>POOL</th>
              </tr>
            </thead>
            <tbody>
              {sortedExotics.map((e, i) => (
                <tr key={i}>
                  <td style={cellStyle}>{e.wager}</td>
                  <td style={{ ...cellStyle, fontFamily: 'var(--font-mono)' }}>{e.winning_numbers}</td>
                  <td style={numStyle}>{e.base || '—'}</td>
                  <td style={{ ...numStyle, color: 'var(--accent-gold-bright)', fontWeight: 600 }}>{e.payoff}</td>
                  <td style={numStyle}>{e.pool || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {/* Also-rans */}
      {debrief.also_ran?.length > 0 && (
        <Section label="ALSO RAN">
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            {debrief.also_ran.join(', ')}
          </p>
        </Section>
      )}

      {/* Scratches */}
      {debrief.scratches?.length > 0 && (
        <Section label="SCRATCHES">
          <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
            {debrief.scratches.join(', ')}
          </p>
        </Section>
      )}
      </div>

      {/* Pre-race prediction comparison */}
      {debrief.prediction_check?.contenders?.length > 0 && (
        <div style={{
          padding: '10px 14px',
          background: 'rgba(26,107,168,0.08)',
          borderRadius: 'var(--radius-md)',
          borderLeft: '3px solid var(--accent-blue)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-blue-bright)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <Icon name="lightbulb" size={12} color="var(--accent-blue-bright)" /> PRE-RACE CONTENDERS
            </span>
          </div>
          {debrief.prediction_check.contenders.map((c, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' }}>
              <span style={{ color: 'var(--text-secondary)' }}>{c.horse}</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: c.actual_finish === '1' ? '#FFD700' : c.actual_finish === '2' ? '#C0C0C0' : c.actual_finish === '3' ? '#CD7F32' : 'var(--text-muted)' }}>
                {c.actual_finish === 'Out of money' ? c.actual_finish : `Finished ${c.actual_finish}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
