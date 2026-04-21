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
            Secretariat is reviewing the race result…
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
    hit:     { cls: 'badge-green', label: '✓ CALLED IT' },
    miss:    { cls: 'badge-red',   label: '✗ MISSED' },
    partial: { cls: 'badge-gold',  label: '~ PARTIAL' },
  };
  const accBadge = debrief.prediction_accuracy
    ? accuracyCfg[debrief.prediction_accuracy.toLowerCase()]
    : null;

  const Section = ({ label, children }) => (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 13,
        color: 'var(--text-muted)',
        letterSpacing: '0.06em',
        marginBottom: 6,
      }}>
        {label}
      </div>
      {children}
    </div>
  );

  return (
    <div style={{ padding: '0 0 8px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--accent-gold)' }}>
          RACE DEBRIEF
        </span>
        {accBadge && (
          <span className={`badge ${accBadge.cls}`}>{accBadge.label}</span>
        )}
      </div>

      {/* Headline */}
      <p style={{ fontSize: 16, fontStyle: 'italic', color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 16 }}>
        "{debrief.headline}"
      </p>

      {/* What happened */}
      <Section label="RACE STORY">
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {debrief.what_happened}
        </p>
      </Section>

      {/* Why winner won */}
      <Section label="WINNER ANALYSIS">
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {debrief.why_winner_won}
        </p>
      </Section>

      {/* Prediction vs reality */}
      {debrief.prediction_notes && (
        <div style={{
          padding: '10px 14px',
          background: 'rgba(26,107,168,0.08)',
          borderRadius: 'var(--radius-md)',
          borderLeft: '3px solid var(--accent-blue)',
          marginBottom: 16,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-blue-bright)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            VS PRE-RACE PREDICTION
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {debrief.prediction_notes}
          </p>
        </div>
      )}

      {/* Notable losers */}
      {debrief.notable_losers?.length > 0 && (
        <Section label="NOTABLE RUNS">
          {debrief.notable_losers.map((item, i) => (
            <div key={i} style={{ marginBottom: 6 }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{item.horse}</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>— {item.note}</span>
            </div>
          ))}
        </Section>
      )}

      {/* Key takeaway */}
      <div style={{
        padding: '10px 14px',
        background: 'rgba(201,162,39,0.08)',
        borderRadius: 'var(--radius-md)',
        borderLeft: '3px solid var(--accent-gold)',
        marginBottom: 12,
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-gold)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Icon name="lightbulb" size={12} color="var(--accent-gold)" /> KEY TAKEAWAY</span>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {debrief.key_takeaway}
        </p>
      </div>

      {/* Beginner lesson */}
      <div style={{
        padding: '10px 14px',
        background: 'rgba(26,107,168,0.06)',
        borderRadius: 'var(--radius-md)',
        borderLeft: '3px solid var(--accent-blue)',
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-blue-bright)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Icon name="learn" size={12} color="var(--accent-blue-bright)" /> BEGINNER LESSON</span>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {debrief.beginner_lesson}
        </p>
      </div>
    </div>
  );
}
