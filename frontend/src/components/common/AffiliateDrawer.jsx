import { useEffect } from 'react';
import { getAffiliatesForRegion, buildAffiliateUrl, trackAffiliateClick as logAffiliateBackend } from '../../utils/affiliates';
import { trackAffiliateClick } from '../../utils/analytics';

function openAffiliate(affiliate, baseUrl, sessionId, onClose) {
  trackAffiliateClick(affiliate.id, affiliate.name, null);
  logAffiliateBackend(affiliate.id, sessionId);
  window.open(buildAffiliateUrl(affiliate, baseUrl), '_blank', 'noopener,noreferrer');
  if (onClose) onClose();
}

export default function AffiliateDrawer({ open, onClose, region = 'usa', sessionId = '', recommendedHorse = '', recommendedBet = '' }) {
  // Lock body scroll while open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  const affiliates = getAffiliatesForRegion(region);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.6)',
          zIndex: 200,
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 201,
        background: 'var(--bg-elevated)',
        borderRadius: '16px 16px 0 0',
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column',
        animation: 'slideInUp 0.25s ease-out',
      }}>
        <style>{`
          @keyframes slideInUp {
            from { transform: translateY(100%); }
            to   { transform: translateY(0); }
          }
        `}</style>

        {/* Handle */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 4px' }}>
          <div style={{ width: 40, height: 4, borderRadius: 2, background: 'var(--border-medium)' }} />
        </div>

        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 20px 16px',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--accent-gold)' }}>
              PLACE YOUR BETS
            </div>
            {recommendedHorse ? (
              <div style={{ fontSize: 12, color: 'var(--accent-gold-bright)', marginTop: 2 }}>
                Secretariat recommends: <strong>{recommendedHorse}</strong>
                {recommendedBet && <span style={{ color: 'var(--text-muted)' }}> · {recommendedBet}</span>}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                Open your sportsbook and place this bet:
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: 22,
              lineHeight: 1,
              padding: 4,
            }}
          >
            ×
          </button>
        </div>

        {/* Affiliate cards */}
        <div style={{ overflowY: 'auto', padding: '12px 16px', flex: 1 }}>
          {affiliates.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: 13 }}>
              No sportsbooks available for your region.
            </div>
          ) : (
            affiliates.map((affiliate) => (
              <div
                key={affiliate.id}
                style={{
                  background: 'var(--bg-card)',
                  borderRadius: 'var(--radius-md)',
                  border: affiliate.featured
                    ? '1px solid var(--border-gold)'
                    : '1px solid var(--border-subtle)',
                  padding: '14px 16px',
                  marginBottom: 10,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                }}
              >
                {/* Logo placeholder */}
                <div style={{
                  width: 48,
                  height: 48,
                  borderRadius: 10,
                  background: 'var(--bg-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  flexShrink: 0,
                }}>
                  {affiliate.logo}
                </div>

                {/* Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                    <span style={{ fontWeight: 700, fontSize: 15 }}>{affiliate.name}</span>
                    {affiliate.featured && (
                      <span className="badge badge-gold" style={{ fontSize: 9 }}>FEATURED</span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                    {affiliate.tagline}
                  </div>
                </div>

                {/* CTA — single button or sub-options */}
                {affiliate.subOptions ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 }}>
                    {affiliate.subOptions.map((opt) => (
                      <button
                        key={opt.label}
                        onClick={() => openAffiliate(affiliate, opt.baseUrl, sessionId, onClose)}
                        className="btn btn-primary"
                        style={{ fontSize: 11, padding: '6px 12px', whiteSpace: 'nowrap' }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <button
                    onClick={() => openAffiliate(affiliate, affiliate.baseUrl, sessionId, onClose)}
                    className="btn btn-primary"
                    style={{ flexShrink: 0, fontSize: 12, padding: '8px 14px' }}
                  >
                    {affiliate.cta}
                  </button>
                )}
              </div>
            ))
          )}
        </div>

        {/* Responsible gambling footer */}
        <div style={{
          padding: '12px 20px 24px',
          borderTop: '1px solid var(--border-subtle)',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
            🔞 18+ only. Gambling involves risk. If you're struggling, visit{' '}
            <a
              href="https://www.ncpgambling.org"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--accent-blue-bright)' }}
            >
              ncpgambling.org
            </a>{' '}
            (US) or{' '}
            <a
              href="https://www.begambleaware.org"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--accent-blue-bright)' }}
            >
              BeGambleAware.org
            </a>{' '}
            (UK/AU).
          </div>
        </div>
      </div>
    </>
  );
}
