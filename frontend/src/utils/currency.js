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
