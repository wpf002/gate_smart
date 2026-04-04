import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function PageHeader({ title, subtitle, showBack = false, right = null }) {
  const navigate = useNavigate();

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '14px 16px',
      borderBottom: '1px solid var(--border-subtle)',
      position: 'sticky',
      top: 0,
      background: 'var(--bg-primary)',
      zIndex: 10,
    }}>
      {showBack && (
        <button
          onClick={() => navigate(-1)}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontSize: 20,
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          ←
        </button>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 20,
          color: 'var(--accent-gold)',
          letterSpacing: '0.04em',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {title}
        </div>
        {subtitle && (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 1 }}>
            {subtitle}
          </div>
        )}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}
