const { test } = require('node:test');
const assert = require('node:assert/strict');

process.env.MCP_JWT_SECRET = 'x'.repeat(32);
process.env.MCP_JWT_ISSUER = 'azzas-mcp';

const { issueTokens, decodeToken } = require('../_helpers/jwt');
const handler = require('../auth/refresh');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.json = (o) => { r.body = o; return r; };
  r.send = (o) => { r.body = o; return r; };
  r.end = () => r;
  return r;
}

test('refresh com refresh válido retorna novo access', async () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: process.env.MCP_JWT_SECRET, issuer: 'azzas-mcp', accessTtlS: 1800, refreshTtlS: 604800 });
  const req = { method: 'POST', headers: { authorization: `Bearer ${pair.refresh}` } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 200);
  assert.ok(res.body.access);
  assert.ok(typeof res.body.access_exp === 'number');
  const claims = decodeToken(res.body.access, process.env.MCP_JWT_SECRET, 'azzas-mcp');
  assert.equal(claims.kind, 'access');
  assert.equal(claims.email, 'a@azzas.com.br');
});

test('refresh com access token como refresh rejeita 401', async () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: process.env.MCP_JWT_SECRET, issuer: 'azzas-mcp', accessTtlS: 1800, refreshTtlS: 604800 });
  const req = { method: 'POST', headers: { authorization: `Bearer ${pair.access}` } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 401);
});

test('refresh sem header rejeita 401', async () => {
  const req = { method: 'POST', headers: {} };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 401);
});

test('refresh com Bearer malformado rejeita 401', async () => {
  const req = { method: 'POST', headers: { authorization: 'Basic abc' } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 401);
});

test('refresh com signature errada rejeita 401', async () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: 'y'.repeat(32), issuer: 'azzas-mcp', accessTtlS: 1800, refreshTtlS: 604800 });
  const req = { method: 'POST', headers: { authorization: `Bearer ${pair.refresh}` } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 401);
});

test('refresh 405 em GET', async () => {
  const res = mockRes();
  await handler({ method: 'GET', headers: {} }, res);
  assert.equal(res.statusCode, 405);
});
