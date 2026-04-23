const { test } = require('node:test');
const assert = require('node:assert/strict');
const handler = require('../version');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.json = (o) => { r.body = o; return r; };
  r.send = (o) => { r.body = o; return r; };
  return r;
}

test('version retorna latest e min', async () => {
  const res = mockRes();
  await handler({ method: 'GET' }, res);
  assert.equal(res.statusCode, 200);
  assert.ok(res.body.latest);
  assert.ok(res.body.min);
});

test('version rejeita POST com 405', async () => {
  const res = mockRes();
  await handler({ method: 'POST' }, res);
  assert.equal(res.statusCode, 405);
});
