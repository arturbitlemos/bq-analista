import { describe, it, expect } from 'vitest';
import { issueTokens, decodeToken, refreshAccess } from '../src/jwt';

const SECRET = 'x'.repeat(32);
const ISSUER = 'azzas-mcp';

describe('jwt', () => {
  it('issueTokens produz access e refresh com kind correto', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    const accessClaims = decodeToken(pair.access, SECRET, ISSUER);
    const refreshClaims = decodeToken(pair.refresh, SECRET, ISSUER);
    expect(accessClaims.kind).toBe('access');
    expect(refreshClaims.kind).toBe('refresh');
    expect(accessClaims.email).toBe('foo@azzas.com.br');
    expect(accessClaims.sub).toBe('foo@azzas.com.br');
    expect(accessClaims.iss).toBe(ISSUER);
  });

  it('decodeToken rejeita signature inválida', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    expect(() => decodeToken(pair.access, 'wrong-secret'.repeat(3), ISSUER)).toThrow();
  });

  it('decodeToken rejeita issuer errado', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    expect(() => decodeToken(pair.access, SECRET, 'other-issuer')).toThrow();
  });

  it('refreshAccess aceita refresh válido, rejeita access como refresh', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    const newAccess = refreshAccess(pair.refresh, SECRET, ISSUER, 1800);
    expect(decodeToken(newAccess, SECRET, ISSUER).kind).toBe('access');
    expect(() => refreshAccess(pair.access, SECRET, ISSUER, 1800)).toThrow(/not a refresh/);
  });

  it('issueTokens rejeita secret com menos de 32 bytes', () => {
    expect(() => issueTokens({
      email: 'foo@azzas.com.br',
      secret: 'short',
      issuer: ISSUER,
      accessTtlS: 1800,
      refreshTtlS: 604800,
    })).toThrow(/at least 32 bytes/);
  });

  it('decodeToken rejeita secret com menos de 32 bytes', () => {
    expect(() => decodeToken('fake.token.here', 'short', ISSUER)).toThrow(/at least 32 bytes/);
  });
});
