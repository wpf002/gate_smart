import { useEffect, useState } from 'react';
import { getAffiliatesForRegion, buildAffiliateUrl, trackAffiliateClick as logAffiliateBackend } from '../../utils/affiliates';
import { trackAffiliateClick } from '../../utils/analytics';

// Sportsbooks don't accept pre-filled bet slips from outside links, so the
// closest thing to one-click is putting the exact bet on the clipboard as the
// user leaves: they open the race and paste or read it off.
async function copyBet(text) {
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function openAffiliate(affiliate, baseUrl, sessionId, onClose, betText = '') {
  copyBet(betText);
  trackAffiliateClick(affiliate.id, affiliate.name, null);
  logAffiliateBackend(affiliate.id, sessionId);
  window.open(buildAffiliateUrl(affiliate, baseUrl), '_blank', 'noopener,noreferrer');
  if (onClose) onClose();
}

export default function AffiliateDrawer({ open, onClose, region = 'usa', sessionId = '', recommendedHorse = '', recommendedBet = '', betText = '' }) {
  const [copied, setCopied] = useState(false);
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
              PLACE YOUR BET
            </div>
            {recommendedHorse ? (
              <div style={{ fontSize: 12, color: 'var(--accent-gold-bright)', marginTop: 2 }}>
                Secretariat recommends: <strong>{recommendedHorse}</strong>
                {recommendedBet && <span style={{ color: 'var(--text-muted)' }}> · {recommendedBet}</span>}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                Choose your advance deposit wagering platform:
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

        {/* The exact bet, ready to paste into whichever sportsbook they pick */}
        {betText && (
          <div style={{ margin: '12px 16px 0', padding: '10px 12px', background: 'var(--bg-card)', border: '1px dashed var(--border-gold)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: 11, letterSpacing: '0.06em', color: 'var(--accent-gold)' }}>YOUR BET</span>
              <button
                onClick={async () => { if (await copyBet(betText)) { setCopied(true); setTimeout(() => setCopied(false), 2000); } }}
                style={{ background: 'none', border: 'none', color: 'var(--accent-gold-bright)', fontSize: 12, cursor: 'pointer' }}
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>{betText}</pre>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>Copied automatically when you tap Place Bet.</div>
          </div>
        )}

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
                {/* Logo */}
                <div style={{
                  width: 48,
                  height: 48,
                  borderRadius: 10,
                  background: 'var(--bg-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 14,
                  fontWeight: 700,
                  flexShrink: 0,
                  overflow: 'hidden',
                }}>
                  {affiliate.logoUrl
                    ? <img src={affiliate.logoUrl} alt={affiliate.name} style={{ width: 32, height: 32, objectFit: 'contain' }} />
                    : affiliate.logo}
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
                        onClick={() => openAffiliate(affiliate, opt.baseUrl, sessionId, onClose, betText)}
                        className="btn btn-primary"
                        style={{ fontSize: 11, padding: '6px 12px', whiteSpace: 'nowrap' }}
                      >
                        Place Bet
                      </button>
                    ))}
                  </div>
                ) : (
                  <button
                    onClick={() => openAffiliate(affiliate, affiliate.baseUrl, sessionId, onClose, betText)}
                    className="btn btn-primary"
                    style={{ flexShrink: 0, fontSize: 12, padding: '8px 16px' }}
                  >
                    Place Bet
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
            18+ only. Gambling involves risk. If you need help, visit{' '}
            <a
              href="https://www.ncpgambling.org"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--accent-blue-bright)' }}
            >
              ncpgambling.org
            </a>
            .
          </div>
        </div>
      </div>
    </>
  );
}
