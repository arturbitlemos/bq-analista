const { test } = require('node:test');
const assert = require('node:assert/strict');

process.env.AZURE_CLIENT_ID = 'test-client-id';
process.env.AZURE_TENANT_ID = 'test-tenant-id';
process.env.SESSION_SECRET = 'z'.repeat(32);

const handler = require('../auth/_handlers/start');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.send = (b) => { r.body = b; return r; };
  r.end = (b) => { r.body = b ?? r.body; return r; };
  return r;
}

test('start 302 pro Azure quando redirect_uri é loopback válido e nonce presente', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:8765/cb', nonce: 'abcd1234' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  assert.match(res.headers['location'], /login\.microsoftonline\.com.*authorize/);
  assert.match(res.headers['set-cookie'] ?? '', /mcp_oauth_state=/);
});

test('state no Location bate com mcp_oauth_state no cookie', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:8765/cb', nonce: 'abcd1234' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);

  // Extract state from Location URL
  const loc = new URL(res.headers['location']);
  const stateInUrl = loc.searchParams.get('state');

  // Extract state from Set-Cookie header
  const cookieHeader = res.headers['set-cookie'] ?? '';
  const cookieMatch = cookieHeader.match(/mcp_oauth_state=([^;]+)/);
  assert.ok(cookieMatch, 'Set-Cookie deve conter mcp_oauth_state');
  const stateInCookie = cookieMatch[1];

  assert.equal(stateInUrl, stateInCookie);
});

test('start rejeita redirect_uri fora de loopback', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'https://evil.com/cb', nonce: 'abcd1234' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('start rejeita porta fora do range 8765-8799', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:3000/cb', nonce: 'abcd1234' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('start rejeita nonce ausente', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:8765/cb' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('start rejeita nonce muito curto (< 8 chars)', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:8765/cb', nonce: 'abc' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('start rejeita nonce com caracteres inválidos', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:8765/cb', nonce: 'abc!@#$%^&*' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('start 405 em method errado', async () => {
  const req = { method: 'POST', query: {}, headers: { host: 'bq-analista.vercel.app' } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 405);
});
