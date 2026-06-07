const REGION_CURRENCY = {
  gb:  { symbol: '£', code: 'GBP' },
  ire: { symbol: '€', code: 'EUR' },
  usa: { symbol: '$', code: 'USD' },
  can: { symbol: 'C$', code: 'CAD' },
  aus: { symbol: 'A$', code: 'AUD' },
  fra: { symbol: '€', code: 'EUR' },
};

export function getCurrencySymbol(region) {
  const r = (region || 'usa').toLowerCase();
  return REGION_CURRENCY[r]?.symbol || '$';
}

export function formatCurrency(amount, region) {
  const symbol = getCurrencySymbol(region);
  if (amount == null || isNaN(amount)) return null;
  return `${symbol}${Number(amount).toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

export function formatPurse(purseString, region) {
  if (!purseString) return '';
  const num = parseFloat(String(purseString).replace(/[^0-9.]/g, ''));
  if (isNaN(num)) return String(purseString);
  return formatCurrency(num, region);
}

/**
 * Safe claiming-price formatter. Returns "$25,000" for a valid amount, or null
 * for missing/zero/non-numeric input — so a stray "N/A" or empty value can
 * never render as "$NaN".
 */
export function formatClaim(value) {
  if (value == null || value === '') return null;
  const num = typeof value === 'number'
    ? value
    : parseFloat(String(value).replace(/[^0-9.]/g, ''));
  if (!Number.isFinite(num) || num <= 0) return null;
  return `$${num.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}
