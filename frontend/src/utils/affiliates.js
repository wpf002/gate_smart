import { logAffiliateClick } from './api';

// Affiliate sportsbook configuration
export const AFFILIATES = [
  {
    id: 'draftkings',
    name: 'DraftKings',
    logo: '🏈',
    tagline: 'Bet $5, Get $150 in Bonus Bets',
    regions: ['usa'],
    featured: true,
    utmParams: { utm_source: 'gatesmart', utm_medium: 'affiliate', utm_campaign: 'horses' },
    subOptions: [
      { label: 'DraftKings Racing', baseUrl: 'https://racing.draftkings.com' },
      { label: 'DK Horse',          baseUrl: 'https://www.dkhorse.com' },
    ],
  },
  {
    id: 'fanduel',
    name: 'FanDuel',
    logo: '🎯',
    tagline: 'No Sweat First Bet up to $1,000',
    cta: 'Claim Offer',
    baseUrl: 'https://fanduel.com/racing',
    utmParams: { utm_source: 'gatesmart', utm_medium: 'affiliate', utm_campaign: 'horses' },
    regions: ['usa'],
    featured: true,
  },
  {
    id: 'tvg',
    name: 'TVG',
    logo: '🏇',
    tagline: "America's #1 Horse Racing App",
    cta: 'Bet Horses',
    baseUrl: 'https://tvg.com',
    utmParams: { utm_source: 'gatesmart', utm_medium: 'affiliate', utm_campaign: 'horses' },
    regions: ['usa'],
    featured: false,
  },
  {
    id: 'betfair',
    name: 'Betfair',
    logo: '📊',
    tagline: 'Exchange Betting — Best Odds',
    cta: 'Open Account',
    baseUrl: 'https://betfair.com/exchange/plus/en/horse-racing-betting',
    utmParams: { utm_source: 'gatesmart', utm_medium: 'affiliate', utm_campaign: 'horses' },
    regions: ['uk', 'australia'],
    featured: true,
  },
  {
    id: 'bet365',
    name: 'Bet365',
    logo: '🌐',
    tagline: 'Up to £30 in Free Bets',
    cta: 'Join Now',
    baseUrl: 'https://bet365.com',
    utmParams: { utm_source: 'gatesmart', utm_medium: 'affiliate', utm_campaign: 'horses' },
    regions: ['uk', 'australia'],
    featured: true,
  },
  {
    id: 'william_hill',
    name: 'William Hill',
    logo: '⚡',
    tagline: '£30 Free Bet for New Customers',
    cta: 'Bet Now',
    baseUrl: 'https://williamhill.com',
    utmParams: { utm_source: 'gatesmart', utm_medium: 'affiliate', utm_campaign: 'horses' },
    regions: ['uk'],
    featured: false,
  },
  {
    id: 'sportsbet',
    name: 'Sportsbet',
    logo: '🦘',
    tagline: 'Fast Racing Markets & Best Tote',
    cta: 'Get Started',
    baseUrl: 'https://sportsbet.com.au',
    utmParams: { utm_source: 'gatesmart', utm_medium: 'affiliate', utm_campaign: 'horses' },
    regions: ['australia'],
    featured: false,
  },
];

export function getAffiliatesForRegion(region = 'usa') {
  const normalized = region.toLowerCase();
  const filtered = AFFILIATES.filter((a) => a.regions.includes(normalized));
  // Featured first
  return [...filtered.filter((a) => a.featured), ...filtered.filter((a) => !a.featured)];
}

export function buildAffiliateUrl(affiliate, baseUrl = affiliate.baseUrl) {
  const params = new URLSearchParams(affiliate.utmParams).toString();
  return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}${params}`;
}

export function trackAffiliateClick(affiliateId, sessionId = '', raceId = '') {
  logAffiliateClick(affiliateId, sessionId, raceId).catch(() => null);
}
