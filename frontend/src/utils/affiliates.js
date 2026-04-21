import { logAffiliateClick } from './api';

// ── Content partner configuration ──────────────────────────────────────────────
export const PARTNERS = {
  thorograph: {
    name: 'Thoro-Graph',
    url: 'https://www.thorograph.com',
    description: 'Proprietary speed figures used by serious handicappers — especially valuable on turf and off tracks.',
    cta: 'Get TG Figures',
  },
  westpoint: {
    name: 'West Point Thoroughbreds',
    url: 'https://www.westpointtb.com',
    description: 'Own a share of a top-level thoroughbred racehorse. The gold standard in racing partnerships.',
    cta: 'Explore Ownership',
  },
};

export function getPartnerUrl(partnerKey) {
  return PARTNERS[partnerKey]?.url || '#';
}

// North American ADW (Advance Deposit Wagering) partners
// Affiliate tracking URLs will be added when agreements are signed.
export const AFFILIATES = [
  {
    id: 'twinspires',
    name: 'TwinSpires',
    logo: 'TS',
    logoUrl: 'https://www.google.com/s2/favicons?domain=twinspires.com&sz=64',
    tagline: 'Official wagering partner of the Kentucky Derby. Bet on every North American thoroughbred race.',
    cta: 'Bet Now',
    baseUrl: 'https://www.twinspires.com',
    regions: ['usa', 'can'],
    featured: true,
  },
  {
    id: 'nyrabets',
    name: 'NYRA Bets',
    logo: 'NYRA',
    logoUrl: 'https://www.google.com/s2/favicons?domain=nyrabets.com&sz=64',
    tagline: 'Official wagering platform of the New York Racing Association. Home of Saratoga, Belmont, and Aqueduct.',
    cta: 'Bet Now',
    baseUrl: 'https://www.nyrabets.com',
    regions: ['usa', 'can'],
    featured: true,
  },
  {
    id: 'tvg',
    name: 'TVG',
    logo: 'TVG',
    logoUrl: 'https://www.google.com/s2/favicons?domain=tvg.com&sz=64',
    tagline: "America's leading horse racing network and wagering platform.",
    cta: 'Bet Horses',
    baseUrl: 'https://www.tvg.com',
    regions: ['usa', 'can'],
    featured: false,
  },
  {
    id: 'amwager',
    name: 'AmWager',
    logo: 'AMW',
    logoUrl: 'https://www.google.com/s2/favicons?domain=amwager.com&sz=64',
    tagline: 'Premier advance deposit wagering platform for North American racing.',
    cta: 'Get Started',
    baseUrl: 'https://www.amwager.com',
    regions: ['usa', 'can'],
    featured: false,
  },
];

export function getAffiliatesForRegion(region = 'usa') {
  const normalized = region.toLowerCase();
  const filtered = AFFILIATES.filter((a) => a.regions.includes(normalized));
  return [...filtered.filter((a) => a.featured), ...filtered.filter((a) => !a.featured)];
}

export function buildAffiliateUrl(affiliate, baseUrl = affiliate.baseUrl) {
  return baseUrl;
}

export function trackAffiliateClick(affiliateId, sessionId = '', raceId = '') {
  logAffiliateClick(affiliateId, sessionId, raceId).catch(() => null);
}
