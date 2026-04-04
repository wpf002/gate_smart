import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRacesToday, getRacesByDate } from '../utils/api';
import { RaceCard, RaceCardSkeleton } from '../components/races/RaceCard';
import PageHeader from '../components/common/PageHeader';

function DateTabs({ selected, onChange }) {
  const today = new Date();
  const tabs = [-1, 0, 1].map((offset) => {
    const d = new Date(today);
    d.setDate(d.getDate() + offset);
    const iso = d.toISOString().split('T')[0];
    const label = offset === 0 ? 'Today' : offset === -1 ? 'Yesterday' : 'Tomorrow';
    return { iso, label };
  });

  return (
    <div style={{ display: 'flex', gap: 6, padding: '10px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
      {tabs.map(({ iso, label }) => (
        <button
          key={iso}
          onClick={() => onChange(iso)}
          style={{
            flex: 1,
            padding: '6px 0',
            borderRadius: 8,
            border: 'none',
            background: selected === iso ? 'rgba(201,162,39,0.15)' : 'transparent',
            color: selected === iso ? 'var(--accent-gold-bright)' : 'var(--text-secondary)',
            fontFamily: 'var(--font-body)',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export default function HomePage() {
  const today = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState(today);

  const isToday = selectedDate === today;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['races', selectedDate],
    queryFn: () => isToday ? getRacesToday() : getRacesByDate(selectedDate),
  });

  const races = data?.racecards ?? data?.races ?? data ?? [];

  return (
    <div>
      <PageHeader
        title="GATESMART"
        subtitle="AI-powered racing intelligence"
        right={
          <button
            onClick={() => window.location.reload()}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}
          >
            ↻
          </button>
        }
      />

      <DateTabs selected={selectedDate} onChange={setSelectedDate} />

      <div style={{ padding: '12px 16px' }}>
        {isError && (
          <div style={{
            padding: 16,
            background: 'rgba(192,57,43,0.1)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--accent-red-bright)',
            fontSize: 13,
            marginBottom: 12,
          }}>
            Failed to load races. Check your connection.
          </div>
        )}

        {isLoading ? (
          [...Array(6)].map((_, i) => <RaceCardSkeleton key={i} />)
        ) : races.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '40px 20px',
            color: 'var(--text-muted)',
          }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🏇</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 20 }}>No races found</div>
            <div style={{ fontSize: 13, marginTop: 6 }}>Try a different date</div>
          </div>
        ) : (
          races.map((race) => (
            <RaceCard key={race.race_id || race.id} race={race} />
          ))
        )}
      </div>
    </div>
  );
}
