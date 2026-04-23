const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');

process.env.AZURE_CLIENT_ID = 'test-client-id';
process.env.AZURE_TENANT_ID = 'tenant-azzas';
process.env.AZURE_CLIENT_SECRET = 'test-secret';
process.env.SESSION_SECRET = 'z'.repeat(32);
process.env.MCP_JWT_SECRET = 'x'.repeat(32);
process.env.MCP_JWT_ISSUER = 'azzas-mcp';

const { signState } = require('../_helpers/state');

const REDIRECT = 'http://localhost:8765/cb';
const STATE = signState(REDIRECT, process.env.SESSION_SECRET);

function mockIdToken({ tid = 'tenant-azzas', email = 'foo@azzas.com.br' } = {}) {
  const header = Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ tid, preferred_username: email, email })).toString('base64url');
  return `${header}.${payload}.sig`;
}

function mockRes() {
  const r = { statusCode: 200, headers: {} };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.send = (b) => { r.body = b; return r; };
  r.end = (b) => { r.body = b ?? r.body; return r; };
  return r;
}

function stubFetch(idToken) {
  global.fetch = async () => ({ ok: true, json: async () => ({ id_token: idToken, access_token: 'az-access' }) });
}

beforeEach(() => {
  delete global.fetch;
});

test('callback com tid correto redireciona loopback com tokens', async () => {
  stubFetch(mockIdToken({}));
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'az-code', state: 'placeholder' },
    headers: { cookie: `mcp_oauth_state=${STATE}`, host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  const loc = new URL(res.headers['location']);
  assert.equal(loc.hostname, 'localhost');
  assert.equal(loc.port, '8765');
  assert.ok(loc.searchParams.get('access'));
  assert.ok(loc.searchParams.get('refresh'));
  assert.equal(loc.searchParams.get('email'), 'foo@azzas.com.br');
});

test('callback com tid errado redireciona loopback com error=wrong_tenant', async () => {
  stubFetch(mockIdToken({ tid: 'tenant-errado' }));
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'az-code', state: 'placeholder' },
    headers: { cookie: `mcp_oauth_state=${STATE}`, host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  const loc = new URL(res.headers['location']);
  assert.equal(loc.searchParams.get('error'), 'wrong_tenant');
  assert.equal(loc.searchParams.get('access'), null);
});

test('callback sem cookie rejeita 400', async () => {
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'az-code', state: 'placeholder' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('callback com cookie adulterado rejeita 400', async () => {
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'az-code', state: 'placeholder' },
    headers: { cookie: `mcp_oauth_state=${STATE.replace(/.$/, 'x')}`, host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('callback com code exchange falhando redireciona com error=invalid_code', async () => {
  global.fetch = async () => ({ ok: false, status: 400, json: async () => ({ error: 'invalid_grant' }) });
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'bad-code', state: 'placeholder' },
    headers: { cookie: `mcp_oauth_state=${STATE}`, host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  const loc = new URL(res.headers['location']);
  assert.equal(loc.searchParams.get('error'), 'invalid_code');
});

test('callback 405 em method errado', async () => {
  const handler = require('../auth/callback');
  const res = mockRes();
  await handler({ method: 'POST', query: {}, headers: {} }, res);
  assert.equal(res.statusCode, 405);
});
