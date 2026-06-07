import { describe, it, expect } from 'vitest';
import { formatClaim } from '../utils/currency';

describe('formatClaim', () => {
  it('formats a numeric amount', () => {
    expect(formatClaim(25000)).toBe('$25,000');
    expect(formatClaim('25000')).toBe('$25,000');
    expect(formatClaim('$25,000')).toBe('$25,000');
  });

  it('never returns "$NaN" for bad input', () => {
    for (const bad of [null, undefined, '', 'N/A', 'abc', NaN, 0, '0', -5]) {
      const out = formatClaim(bad);
      expect(out).toBeNull();
    }
  });
});
