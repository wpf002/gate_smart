import React, { useState } from 'react';
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

  const { data: horse, isLoading } = useQuery({
    queryKey: ['horse', horseId],
    queryFn: () => getHorse(horseId),
  });

  const explainMutation = useMutation({
    mutationFn: () => explainHorse(horseId),
    onSuccess: setExplanation,
  });

  const formMutation = useMutation({
    mutationFn: () => explainFormString(horse?.form || horse?.last_run_style, horse?.horse_name),
    onSuccess: setFormExplanation,
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
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--text-muted)', marginBottom: 8 }}>
              RECENT FORM
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, color: 'var(--accent-gold-bright)', marginBottom: 10 }}>
              {horse.form || horse.last_run_style}
            </div>
            {!formExplanation && !formMutation.isPending && (
              <button
                className="btn btn-secondary"
                style={{ fontSize: 12, padding: '6px 12px' }}
                onClick={() => formMutation.mutate()}
              >
                Explain this form
              </button>
            )}
            {formMutation.isPending && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Decoding…</span>
            )}
            {formExplanation && (
              <div style={{ marginTop: 10 }}>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 10 }}>
                  {formExplanation.plain_english}
                </p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span className={`badge badge-${
                    formExplanation.trend === 'improving' ? 'green' :
                    formExplanation.trend === 'declining' ? 'red' : 'gold'
                  }`}>
                    {formExplanation.trend}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* AI explanation */}
        {!explanation && !explainMutation.isPending && (
          <button
            className="btn btn-primary btn-full"
            onClick={() => explainMutation.mutate()}
          >
            🤖 Explain this horse
          </button>
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

            <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 12 }}>
              {explanation.verdict}
            </p>

            {explanation.key_stats?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  Key Facts
                </div>
                {explanation.key_stats.map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                    <span style={{ color: 'var(--accent-gold)', flexShrink: 0 }}>•</span>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{s}</span>
                  </div>
                ))}
              </div>
            )}

            {explanation.beginner_explanation && (
              <div style={{
                padding: '8px 12px',
                background: 'rgba(26,107,168,0.1)',
                borderRadius: 8,
                fontSize: 13,
                color: 'var(--text-secondary)',
                borderLeft: '2px solid var(--accent-blue)',
              }}>
                💡 {explanation.beginner_explanation}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
