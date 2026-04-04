import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { searchHorses } from '../utils/api';
import PageHeader from '../components/common/PageHeader';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [submitted, setSubmitted] = useState('');
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['horse-search', submitted],
    queryFn: () => searchHorses(submitted),
    enabled: submitted.length >= 2,
  });

  const horses = data?.horses ?? data?.results ?? data ?? [];

  const handleSearch = () => {
    if (query.trim().length >= 2) setSubmitted(query.trim());
  };

  return (
    <div>
      <PageHeader title="SEARCH" subtitle="Find horses by name" />

      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Horse name…"
            style={{ flex: 1, padding: '10px 14px', fontSize: 14, borderRadius: 'var(--radius-md)' }}
            autoFocus
          />
          <button
            className="btn btn-primary"
            onClick={handleSearch}
            disabled={query.trim().length < 2}
          >
            Search
          </button>
        </div>
      </div>

      <div style={{ padding: '12px 16px' }}>
        {isLoading && submitted && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 56, borderRadius: 10 }} />
            ))}
          </div>
        )}

        {isError && (
          <div style={{ color: 'var(--accent-red-bright)', fontSize: 13, padding: 12 }}>
            Search failed. Try again.
          </div>
        )}

        {!isLoading && submitted && horses.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>🔍</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18 }}>No horses found</div>
            <div style={{ fontSize: 13, marginTop: 6 }}>Try a different name</div>
          </div>
        )}

        {!submitted && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>🐎</div>
            <div style={{ fontSize: 13 }}>Search for any horse to view form, stats, and AI analysis</div>
          </div>
        )}

        {horses.map((horse) => (
          <div
            key={horse.horse_id || horse.id}
            onClick={() => navigate(`/horse/${horse.horse_id || horse.id}`)}
            style={{
              background: 'var(--bg-card)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              marginBottom: 8,
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-card-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-card)')}
          >
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
              {horse.horse_name || horse.name}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              {[horse.trainer, horse.age ? `${horse.age}yo` : null, horse.country]
                .filter(Boolean)
                .join(' · ')}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
