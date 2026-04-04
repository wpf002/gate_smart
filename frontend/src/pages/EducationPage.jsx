import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getGlossary, getBeginnerGuide, getBankrollGuide } from '../utils/api';
import PageHeader from '../components/common/PageHeader';

const TABS = [
  { id: 'guide', label: '📖 Guide' },
  { id: 'bankroll', label: '💰 Bankroll' },
  { id: 'glossary', label: '📚 Glossary' },
];

function GuideSection({ guide }) {
  const [expandedStep, setExpandedStep] = useState(null);
  if (!guide) return null;

  return (
    <div>
      <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--accent-gold)', marginBottom: 4 }}>
        {guide.title}
      </h2>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.5 }}>
        {guide.introduction}
      </p>

      {guide.golden_rules && (
        <div style={{
          background: 'rgba(201,162,39,0.08)',
          border: '1px solid var(--border-gold)',
          borderRadius: 'var(--radius-md)',
          padding: 14,
          marginBottom: 16,
        }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--accent-gold)', marginBottom: 10 }}>
            GOLDEN RULES
          </div>
          {guide.golden_rules.map((rule, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 8 }}>
              <span style={{ color: 'var(--accent-gold)', fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
              <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{rule}</span>
            </div>
          ))}
        </div>
      )}

      {guide.steps?.map((step, i) => (
        <div
          key={i}
          style={{
            background: 'var(--bg-card)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 8,
            border: '1px solid var(--border-subtle)',
            overflow: 'hidden',
          }}
        >
          <button
            onClick={() => setExpandedStep(expandedStep === i ? null : i)}
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '14px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              textAlign: 'left',
              fontFamily: 'var(--font-body)',
            }}
          >
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span style={{
                width: 26, height: 26, borderRadius: '50%',
                background: 'rgba(201,162,39,0.15)',
                border: '1px solid var(--border-gold)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--accent-gold)',
                flexShrink: 0,
              }}>
                {i + 1}
              </span>
              <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>
                {step.title}
              </span>
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
              {expandedStep === i ? '▲' : '▼'}
            </span>
          </button>

          {expandedStep === i && (
            <div style={{ padding: '0 14px 14px' }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
                {step.content}
              </p>
              {step.tip && (
                <div style={{
                  padding: '8px 12px',
                  background: 'rgba(26,107,168,0.1)',
                  borderRadius: 6,
                  borderLeft: '2px solid var(--accent-blue)',
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                }}>
                  💡 {step.tip}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function BankrollSection({ guide }) {
  if (!guide) return null;
  return (
    <div>
      <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--accent-gold)', marginBottom: 4 }}>
        {guide.title}
      </h2>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.5 }}>
        {guide.introduction}
      </p>

      {guide.strategies?.map((strategy, i) => (
        <div key={i} className="card" style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>{strategy.name}</div>
            <span className={`badge badge-${strategy.risk_level === 'low' ? 'green' : strategy.risk_level === 'high' ? 'red' : 'gold'}`}>
              {strategy.risk_level} risk
            </span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 10 }}>
            {strategy.description}
          </p>
          {strategy.session_rules?.map((rule, j) => (
            <div key={j} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
              <span style={{ color: 'var(--accent-gold)', flexShrink: 0 }}>•</span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{rule}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function GlossarySection({ glossary }) {
  const [search, setSearch] = useState('');
  if (!glossary) return null;

  const terms = glossary.terms ?? glossary;
  const filtered = terms.filter(
    (t) =>
      t.term?.toLowerCase().includes(search.toLowerCase()) ||
      t.definition?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search terms…"
        style={{ width: '100%', padding: '10px 14px', marginBottom: 14, fontSize: 14 }}
      />
      {filtered.map((t, i) => (
        <div key={i} style={{
          padding: '12px 14px',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--accent-gold-bright)', marginBottom: 4 }}>
            {t.term}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {t.definition}
          </div>
          {t.example && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>
              e.g. {t.example}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function EducationPage() {
  const [activeTab, setActiveTab] = useState('guide');

  const { data: guide } = useQuery({ queryKey: ['beginner-guide'], queryFn: getBeginnerGuide });
  const { data: bankroll } = useQuery({ queryKey: ['bankroll-guide'], queryFn: getBankrollGuide });
  const { data: glossary } = useQuery({ queryKey: ['glossary'], queryFn: getGlossary });

  return (
    <div>
      <PageHeader title="LEARN" subtitle="Horse racing education" />

      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)' }}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            style={{
              flex: 1,
              padding: '10px 4px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === id ? '2px solid var(--accent-gold)' : '2px solid transparent',
              color: activeTab === id ? 'var(--accent-gold-bright)' : 'var(--text-muted)',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              transition: 'color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div style={{ padding: '16px' }}>
        {activeTab === 'guide' && <GuideSection guide={guide} />}
        {activeTab === 'bankroll' && <BankrollSection guide={bankroll} />}
        {activeTab === 'glossary' && <GlossarySection glossary={glossary} />}
      </div>
    </div>
  );
}
