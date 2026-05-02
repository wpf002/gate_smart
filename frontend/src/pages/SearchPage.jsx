import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { searchHorses } from '../utils/api';
import PageHeader from '../components/common/PageHeader';
import { getDisplayTime } from '../components/races/RaceCard';
import { useAppStore } from '../store';
import Icon from '../components/common/Icon';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [submitted, setSubmitted] = useState('');
  const navigate = useNavigate();
  const timezone = useAppStore((s) => s.userProfile?.timezone);

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
      <PageHeader title="SEARCH" subtitle="Find horses by name" />

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
            <div style={{ marginBottom: 10, display: 'flex', justifyContent: 'center' }}><Icon name="search" size={40} /></div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18 }}>No horses found</div>
            <div style={{ fontSize: 13, marginTop: 8, lineHeight: 1.6, maxWidth: 300, margin: '8px auto 0' }}>
              <strong style={{ color: 'var(--text-secondary)' }}>{submitted}</strong> isn't entered in today's or tomorrow's races.
            </div>
            <div style={{
              marginTop: 14,
              padding: '10px 14px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
              fontSize: 12,
              lineHeight: 1.6,
              textAlign: 'left',
              maxWidth: 320,
              margin: '14px auto 0',
            }}>
              <strong style={{ color: 'var(--text-secondary)' }}>Why?</strong> Horse search only works for runners
              actively entered in upcoming races. Historical horses and those
              not currently entered won't appear — check back on their race day.
            </div>
          </div>
        )}

        {!submitted && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
            <div style={{ marginBottom: 10, display: 'flex', justifyContent: 'center' }}><Icon name="search" size={40} /></div>
            <div className="search-tagline" style={{ fontSize: 13 }}>
              Search by horse name to find entries, form, trainer, and jockey
            </div>
          </div>
        )}

        {horses.map((horse, idx) => {
          const { time: displayTime, label: timeLabel } = getDisplayTime(horse, timezone);
          return (
            <div
              key={horse.horse_id || idx}
              style={{
                background: 'var(--bg-card)',
                borderRadius: 'var(--radius-md)',
                padding: '14px',
                marginBottom: 8,
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
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
                    <div style={{ marginTop: 4 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Form: </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--accent-gold)', letterSpacing: '0.12em' }}>
                        {horse.form}
                      </span>
                    </div>
                  )}
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
                  {horse.course && (
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-gold-bright)' }}>
                      {horse.course}
                    </div>
                  )}
                  {(displayTime || horse.off_time) && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      {displayTime || horse.off_time}
                      {timeLabel && <span style={{ marginLeft: 3 }}>{timeLabel}</span>}
                    </div>
                  )}
                </div>
              </div>

              {/* Action row */}
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                {horse.race_id && (
                  <button
                    className="btn btn-primary"
                    onClick={() => navigate(`/race/${horse.race_id}`)}
                    style={{ fontSize: 12, padding: '5px 12px' }}
                  >
                    View Race →
                  </button>
                )}
                <button
                  className="btn btn-secondary"
                  onClick={() => navigate(`/horse/${horse.horse_id}`)}
                  style={{ fontSize: 12, padding: '5px 12px' }}
                >
                  Horse Profile
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
