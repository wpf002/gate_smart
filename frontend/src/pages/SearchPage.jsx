import { useState } from 'react';
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

  const horses = data?.horses ?? [];

  const handleSearch = () => {
    const q = query.trim();
    if (q.length >= 2) setSubmitted(q);
  };

  return (
    <div>
      <PageHeader title="SEARCH" subtitle="Find horses in today's & tomorrow's races" />

      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Horse name (min. 2 characters)…"
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
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
          Searches runners listed in today's and tomorrow's races
        </p>
      </div>

      <div style={{ padding: '12px 16px' }}>
        {isLoading && submitted && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 70, borderRadius: 10 }} />
            ))}
          </div>
        )}

        {isError && (
          <div style={{
            padding: 14,
            background: 'rgba(192,57,43,0.08)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--accent-red-bright)',
            fontSize: 13,
          }}>
            Search failed. Try again.
          </div>
        )}

        {!isLoading && submitted && horses.length === 0 && !isError && (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>🔍</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18 }}>No horses found</div>
            <div style={{ fontSize: 13, marginTop: 6 }}>
              Try a partial name — searches today's & tomorrow's entries only
            </div>
          </div>
        )}

        {!submitted && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>🐎</div>
            <div style={{ fontSize: 13 }}>
              Search by horse name to find entries, form, trainer, and jockey
            </div>
          </div>
        )}

        {horses.map((horse, idx) => (
          <div
            key={horse.horse_id || idx}
            onClick={() => navigate(`/horse/${horse.horse_id}`)}
            style={{
              background: 'var(--bg-card)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              marginBottom: 8,
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-card-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'var(--bg-card)'}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
                  {horse.horse_name || horse.horse}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {[
                    horse.trainer && `T: ${horse.trainer}`,
                    horse.jockey && `J: ${horse.jockey}`,
                    horse.age && `${horse.age}yo`,
                  ].filter(Boolean).join('  ·  ')}
                </div>
                {horse.form && (
                  <div style={{ marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-gold)' }}>
                    Form: {horse.form}
                  </div>
                )}
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
                {horse.course && (
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-gold-bright)' }}>
                    {horse.course}
                  </div>
                )}
                {horse.off_time && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    {horse.off_time}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
