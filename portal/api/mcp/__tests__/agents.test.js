const { test } = require('node:test');
const assert = require('node:assert/strict');
const handler = require('../agents');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.json = (o) => { r.body = o; return r; };
  r.send = (o) => { r.body = o; return r; };
  return r;
}

test('agents retorna manifesto com min_dxt_version e lista de agentes', async () => {
  const res = mockRes();
  await handler({ method: 'GET' }, res);
  assert.equal(res.statusCode, 200);
  assert.ok(res.body.min_dxt_version);
  assert.ok(Array.isArray(res.body.agents));
  assert.ok(res.body.agents.length > 0);
});

test('cada agente tem name, label, url, tools', async () => {
  const res = mockRes();
  await handler({ method: 'GET' }, res);
  for (const agent of res.body.agents) {
    assert.ok(agent.name);
    assert.ok(agent.label);
    assert.ok(agent.url.startsWith('https://'));
    assert.ok(Array.isArray(agent.tools));
    assert.ok(agent.tools.length >= 7, `agente ${agent.name} deve ter ao menos 7 tools`);
    for (const tool of agent.tools) {
      assert.equal(typeof tool.name, 'string', `tool.name deve ser string em ${agent.name}`);
      assert.equal(typeof tool.inputSchema, 'object', `tool.inputSchema deve ser objeto em ${agent.name}`);
      assert.equal(typeof tool.description, 'string', `tool.description deve ser string em ${agent.name}:${tool.name}`);
    }
  }
});

test('agents inclui cache-control header', async () => {
  const res = mockRes();
  await handler({ method: 'GET' }, res);
  assert.match(res.headers['cache-control'] ?? '', /max-age/);
});

test('agents rejeita POST com 405', async () => {
  const res = mockRes();
  await handler({ method: 'POST' }, res);
  assert.equal(res.statusCode, 405);
});
