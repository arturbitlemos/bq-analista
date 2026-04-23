import { describe, it, expect } from 'vitest';
import { compareSemver, isStale } from '../src/version';

describe('version', () => {
  it('compareSemver', () => {
    expect(compareSemver('1.0.0', '1.0.0')).toBe(0);
    expect(compareSemver('1.0.0', '1.0.1')).toBeLessThan(0);
    expect(compareSemver('1.2.0', '1.1.9')).toBeGreaterThan(0);
    expect(compareSemver('2.0.0', '1.9.9')).toBeGreaterThan(0);
  });
  it('isStale true se current < min', () => {
    expect(isStale('0.9.0', '1.0.0')).toBe(true);
    expect(isStale('1.0.0', '1.0.0')).toBe(false);
    expect(isStale('1.1.0', '1.0.0')).toBe(false);
  });
});
