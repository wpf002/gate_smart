import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getHorse, explainHorse, explainFormString } from '../utils/api';
import PageHeader from '../components/common/PageHeader';

function StatRow({ label, value }) {
  if (!value) return null;
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      padding: '8px 0',
      borderBottom: '1px solid var(--border-subtle)',
      fontSize: 13,
    }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
    </div>
  );
}

export default function HorseDetailPage() {
  const { horseId } = useParams();
  const [explanation, setExplanation] = useState(null);
  const [formExplanation, setFormExplanation] = useState(null);
  const [explainError, setExplainError] = useState(null);
  const [formError, setFormError] = useState(null);

  const { data: horse, isLoading } = useQuery({
    queryKey: ['horse', horseId],
    queryFn: () => getHorse(horseId),
  });

  const explainMutation = useMutation({
    mutationFn: () => explainHorse(horseId),
    onSuccess: (data) => { setExplainError(null); setExplanation(data); },
    onError: (err) => {
      const detail = err?.response?.data?.detail || '';
      setExplainError(
        detail.toLowerCase().includes('credit')
          ? 'Secretariat needs Anthropic API credits. Add credits at console.anthropic.com.'
          : `Analysis failed: ${detail || err.message}`
      );
    },
  });

  const formMutation = useMutation({
    mutationFn: () => explainFormString(horse?.form || horse?.last_run_style, horse?.horse_name),
    onSuccess: (data) => { setFormError(null); setFormExplanation(data); },
    onError: (err) => {
      const detail = err?.response?.data?.detail || '';
      setFormError(
        detail.toLowerCase().includes('credit')
          ? 'Secretariat needs Anthropic API credits. Add credits at console.anthropic.com.'
          : `Form decode failed: ${detail || err.message}`
      );
    },
  });

  if (isLoading) {
    return (
      <div>
        <PageHeader title="HORSE" showBack />
        <div style={{ padding: 16 }}>
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 40, borderRadius: 8, marginBottom: 8 }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={horse?.horse_name || 'Horse'}
        subtitle={horse?.trainer ? `Trained by ${horse.trainer}` : undefined}
        showBack
      />

      <div style={{ padding: '16px' }}>
        {/* Key stats */}
        <div className="card" style={{ marginBottom: 14 }}>
          <StatRow label="Age" value={horse?.age} />
          <StatRow label="Sex" value={horse?.sex} />
          <StatRow label="Colour" value={horse?.colour} />
          <StatRow label="Sire" value={horse?.sire} />
          <StatRow label="Dam" value={horse?.dam} />
          <StatRow label="Trainer" value={horse?.trainer} />
          <StatRow label="Jockey" value={horse?.jockey} />
          <StatRow label="Owner" value={horse?.owner} />
          <StatRow label="Weight" value={horse?.weight} />
          <StatRow label="Rating" value={horse?.rating || horse?.official_rating} />
        </div>

        {/* Form string */}
        {(horse?.form || horse?.last_run_style) && (
          <div className="card" style={{ marginBottom: 14 }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--text-muted)', marginBottom: 4 }}>
              RECENT FORM
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.5 }}>
              Each character = one race, oldest → newest (rightmost = most recent).{' '}
              <span style={{ fontFamily: 'var(--font-mono)' }}>1</span>=won &nbsp;
              <span style={{ fontFamily: 'var(--font-mono)' }}>2–9</span>=finishing position &nbsp;
              <span style={{ fontFamily: 'var(--font-mono)' }}>0</span>=10th or worse &nbsp;
              <span style={{ fontFamily: 'var(--font-mono)' }}>P</span>=pulled up &nbsp;
              <span style={{ fontFamily: 'var(--font-mono)' }}>F</span>=fell &nbsp;
              <span style={{ fontFamily: 'var(--font-mono)' }}>-/</span>=season break
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, color: 'var(--accent-gold-bright)', marginBottom: 6, letterSpacing: '0.15em' }}>
              {horse.form || horse.last_run_style}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10 }}>
              Each figure = finishing position in one race. Specific race names aren't available on the current data plan — click <strong>FORM EXPLANATION</strong> below for a plain English breakdown.
            </div>
            {!formExplanation && !formMutation.isPending && (
              <button
                className="btn btn-secondary"
                style={{ fontSize: 12, padding: '6px 12px' }}
                onClick={() => { setFormError(null); formMutation.mutate(); }}
              >
                FORM EXPLANATION
              </button>
            )}
            {formMutation.isPending && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Decoding…</span>
            )}
            {formError && !formMutation.isPending && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--accent-red-bright)' }}>
                ⚠️ {formError}
              </div>
            )}
            {formExplanation && (
              <div style={{ marginTop: 12 }}>
                {/* Decoded run boxes */}
                {formExplanation.decoded?.length > 0 && (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                    {formExplanation.decoded.map((run, i) => {
                      const r = run.result;
                      const isWin = r === '1';
                      const isPlace = r === '2' || r === '3';
                      const isBad = r === 'P' || r === 'F' || r === 'U' || r === 'R' || r === 'B';
                      const isSep = r === '-' || r === '/';
                      const bg = isWin ? 'var(--accent-green)' : isPlace ? 'var(--accent-gold-dim)' : isBad ? 'var(--accent-red)' : isSep ? 'transparent' : 'var(--bg-elevated)';
                      const color = isSep ? 'var(--text-muted)' : '#fff';
                      return (
                        <div key={i} title={run.meaning} style={{
                          width: isSep ? 'auto' : 32,
                          height: 32,
                          borderRadius: 6,
                          background: bg,
                          border: isSep ? 'none' : '1px solid rgba(255,255,255,0.1)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          fontSize: isSep ? 18 : 14,
                          color,
                          padding: isSep ? '0 2px' : 0,
                          cursor: 'default',
                          flexShrink: 0,
                        }}>
                          {r}
                        </div>
                      );
                    })}
                    <span style={{ alignSelf: 'center', fontSize: 10, color: 'var(--text-muted)', marginLeft: 4 }}>
                      oldest → newest
                    </span>
                  </div>
                )}

                {/* Trend badge */}
                <div style={{ marginBottom: 10 }}>
                  <span className={`badge badge-${
                    formExplanation.trend === 'improving' ? 'green' :
                    formExplanation.trend === 'declining' ? 'red' : 'gold'
                  }`} style={{ fontSize: 12, padding: '3px 10px' }}>
                    {formExplanation.trend === 'improving' ? '↑ Improving' :
                     formExplanation.trend === 'declining' ? '↓ Declining' :
                     formExplanation.trend === 'consistent' ? '→ Consistent' : formExplanation.trend}
                  </span>
                </div>

                {/* Plain English summary */}
                <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.7, marginBottom: 12 }}>
                  {formExplanation.plain_english}
                </p>

                {/* Positive signs + red flags */}
                {(formExplanation.positive_signs?.length > 0 || formExplanation.red_flags?.length > 0) && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {formExplanation.positive_signs?.length > 0 && (
                      <div style={{ background: 'rgba(42,122,75,0.08)', borderRadius: 8, padding: '10px 12px', borderLeft: '3px solid var(--accent-green)' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-green-bright)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Positives</div>
                        {formExplanation.positive_signs.map((s, i) => (
                          <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3, display: 'flex', gap: 6 }}>
                            <span style={{ color: 'var(--accent-green-bright)', flexShrink: 0 }}>✓</span>
                            <span>{s}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {formExplanation.red_flags?.length > 0 && (
                      <div style={{ background: 'rgba(192,57,43,0.08)', borderRadius: 8, padding: '10px 12px', borderLeft: '3px solid var(--accent-red)' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-red-bright)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Watch out</div>
                        {formExplanation.red_flags.map((f, i) => (
                          <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3, display: 'flex', gap: 6 }}>
                            <span style={{ color: 'var(--accent-red-bright)', flexShrink: 0 }}>!</span>
                            <span>{f}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* AI explanation */}
        {!explanation && !explainMutation.isPending && (
          <button
            className="btn btn-primary btn-full"
            onClick={() => { setExplainError(null); explainMutation.mutate(); }}
          >
            Horse Analysis
          </button>
        )}
        {explainError && !explainMutation.isPending && (
          <div style={{
            marginTop: 8,
            padding: '10px 14px',
            background: 'rgba(192,57,43,0.08)',
            borderRadius: 'var(--radius-md)',
            fontSize: 13,
            color: 'var(--accent-red-bright)',
          }}>
            ⚠️ {explainError}
          </div>
        )}

        {explainMutation.isPending && (
          <div style={{
            padding: 16,
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: 'var(--accent-gold)',
              animation: 'pulse 1s infinite',
            }} />
            <span style={{ fontSize: 13, color: 'var(--accent-gold)' }}>
              Secretariat is assessing {horse?.horse_name}…
            </span>
          </div>
        )}

        {explanation && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, var(--bg-secondary) 100%)',
            border: '1px solid var(--border-gold)',
            borderRadius: 'var(--radius-md)',
            padding: 16,
          }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, color: 'var(--accent-gold)', marginBottom: 12 }}>
              SECRETARIAT'S VERDICT
            </div>

            {/* Verdict */}
            {(explanation.verdict || explanation.form_summary) && (
              <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.7, marginBottom: 14 }}>
                {explanation.verdict || explanation.form_summary}
              </p>
            )}

            {/* Strengths + Concerns */}
            {(explanation.strengths?.length > 0 || explanation.concerns?.length > 0) && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
                {explanation.strengths?.length > 0 && (
                  <div style={{ background: 'rgba(42,122,75,0.08)', borderRadius: 8, padding: '10px 12px', borderLeft: '3px solid var(--accent-green)' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-green-bright)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Strengths</div>
                    {explanation.strengths.map((s, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3, display: 'flex', gap: 6 }}>
                        <span style={{ color: 'var(--accent-green-bright)', flexShrink: 0 }}>✓</span>
                        <span>{s}</span>
                      </div>
                    ))}
                  </div>
                )}
                {explanation.concerns?.length > 0 && (
                  <div style={{ background: 'rgba(192,57,43,0.08)', borderRadius: 8, padding: '10px 12px', borderLeft: '3px solid var(--accent-red)' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-red-bright)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Concerns</div>
                    {explanation.concerns.map((c, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3, display: 'flex', gap: 6 }}>
                        <span style={{ color: 'var(--accent-red-bright)', flexShrink: 0 }}>!</span>
                        <span>{c}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Key facts */}
            {explanation.key_stats?.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  Key Facts
                </div>
                {explanation.key_stats.map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 5 }}>
                    <span style={{ color: 'var(--accent-gold)', flexShrink: 0 }}>•</span>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{s}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Beginner tip */}
            {explanation.beginner_explanation && (
              <div style={{
                padding: '10px 12px',
                background: 'rgba(26,107,168,0.1)',
                borderRadius: 8,
                fontSize: 13,
                color: 'var(--text-secondary)',
                borderLeft: '2px solid var(--accent-blue)',
                lineHeight: 1.6,
              }}>
                💡 <strong style={{ color: 'var(--accent-blue-bright)' }}>New to betting?</strong> {explanation.beginner_explanation}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
