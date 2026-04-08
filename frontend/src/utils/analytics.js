/**
 * GateSmart Analytics — GA4 wrapper
 * All functions are silent no-ops if GA4 is not loaded.
 */

export function trackEvent(eventName, params = {}) {
  if (typeof window === 'undefined' || !window.gtag) return;
  window.gtag('event', eventName, params);
}

export function trackPageView(path, title) {
  trackEvent('page_view', {
    page_path: path,
    page_title: title,
  });
}

export function trackAffiliateClick(affiliateId, affiliateName, raceId = null) {
  if (import.meta.env.DEV) {
    console.log('[GateSmart] Affiliate click:', affiliateId, affiliateName);
  }
  trackEvent('affiliate_click', {
    affiliate_id: affiliateId,
    affiliate_name: affiliateName,
    race_id: raceId,
    session_id: localStorage.getItem('gs_session_id') || '',
  });
}

export function trackRaceAnalysis(raceId, mode) {
  trackEvent('race_analysis', {
    race_id: raceId,
    analysis_mode: mode,
  });
}

export function trackBetAdded(betType, horseId, odds) {
  trackEvent('bet_added', {
    bet_type: betType,
    horse_id: horseId,
    odds: odds || '',
  });
}

export function trackPaperBetPlaced(betType, stake) {
  trackEvent('paper_bet_placed', {
    bet_type: betType,
    stake: stake,
  });
}

export function trackScoreCardViewed(raceId) {
  trackEvent('scorecard_viewed', { race_id: raceId });
}

export function trackDebriefViewed(raceId) {
  trackEvent('debrief_viewed', { race_id: raceId });
}
