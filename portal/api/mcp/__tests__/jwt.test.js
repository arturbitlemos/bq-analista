const { test } = require('node:test');
const assert = require('node:assert/strict');
const { issueTokens, decodeToken, refreshAccess } = require('../_helpers/jwt');

const SECRET = 'x'.repeat(32);
const ISSUER = 'mcp-exec-azzas';

test('issueTokens retorna access+refresh com campos corretos', () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
  const a = decodeToken(pair.access, SECRET, ISSUER);
  const r = decodeToken(pair.refresh, SECRET, ISSUER);
  assert.equal(a.kind, 'access');
  assert.equal(r.kind, 'refresh');
  assert.equal(a.email, 'a@azzas.com.br');
  assert.equal(a.sub, 'a@azzas.com.br');
  assert.equal(a.iss, ISSUER);
});

test('decodeToken rejeita secret errado', () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
  assert.throws(() => decodeToken(pair.access, 'y'.repeat(32), ISSUER));
});

test('refreshAccess rejeita access-as-refresh', () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
  assert.throws(() => refreshAccess(pair.access, SECRET, ISSUER, 1800), /not a refresh/);
});
