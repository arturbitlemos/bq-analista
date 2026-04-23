const { test } = require('node:test');
const assert = require('node:assert/strict');

process.env.AZURE_CLIENT_ID = 'test-client-id';
process.env.AZURE_TENANT_ID = 'test-tenant-id';
process.env.SESSION_SECRET = 'z'.repeat(32);

const handler = require('../auth/start');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.send = (b) => { r.body = b; return r; };
  r.end = (b) => { r.body = b ?? r.body; return r; };
  return r;
}

test('start 302 pro Azure quando redirect_uri é loopback válido', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:8765/cb' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  assert.match(res.headers['location'], /login\.microsoftonline\.com.*authorize/);
  assert.match(res.headers['set-cookie'] ?? '', /mcp_oauth_state=/);
});

test('start rejeita redirect_uri fora de loopback', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'https://evil.com/cb' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('start rejeita porta fora do range 8765-8799', async () => {
  const req = {
    method: 'GET',
    query: { redirect_uri: 'http://localhost:3000/cb' },
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
