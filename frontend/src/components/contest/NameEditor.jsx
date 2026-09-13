import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { setDisplayName } from '../../utils/api';

/**
 * Leaderboard display name with inline editing. `renderIdle(startEditing)`
 * lets a page style the name itself; the default is a small "Name · Edit Name"
 * link.
 */
export default function NameEditor({ current, renderIdle }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  const start = () => {
    setValue(current.startsWith('Handicapper ') ? '' : current);
    setError('');
    setEditing(true);
  };

  const save = async () => {
    setError('');
    try {
      await setDisplayName(value);
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ['contest-me'] });
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not save that name');
    }
  };

  if (!editing) {
    if (renderIdle) return renderIdle(start);
    return (
      <button onClick={start}
        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer', padding: 0 }}>
        {current} · Edit Name
      </button>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
      <input value={value} maxLength={40} onChange={(e) => setValue(e.target.value)} placeholder="Leaderboard name"
        onKeyDown={(e) => e.key === 'Enter' && save()}
        style={{ flex: 1, minWidth: 140, fontSize: 14, padding: '7px 10px' }} autoFocus />
      <button className="btn btn-primary" style={{ fontSize: 12, padding: '6px 12px' }} onClick={save}>Save</button>
      <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 12px' }} onClick={() => setEditing(false)}>Cancel</button>
      {error && <span style={{ width: '100%', fontSize: 12, color: 'var(--accent-red-bright)' }}>{error}</span>}
    </div>
  );
}
