const { test } = require('node:test');
const assert = require('node:assert/strict');
const { signState, verifyState } = require('../_helpers/state');

const SECRET = 'z'.repeat(32);

test('roundtrip state preserva redirectUri', () => {
  const signed = signState('http://localhost:8765/cb', SECRET);
  const result = verifyState(signed, SECRET);
  assert.equal(result.redirectUri, 'http://localhost:8765/cb');
});

test('tamper rejeitado', () => {
  const signed = signState('http://localhost:8765/cb', SECRET);
  const tampered = signed.replace('8765', '9999');
  assert.equal(verifyState(tampered, SECRET), null);
});

test('secret errado rejeitado', () => {
  const signed = signState('http://localhost:8765/cb', SECRET);
  assert.equal(verifyState(signed, 'y'.repeat(32)), null);
});

test('signState rejeita secret curto', () => {
  assert.throws(() => signState('http://localhost:8765/cb', 'short'), /at least 32 bytes/);
});

test('verifyState retorna null com secret curto', () => {
  const signed = signState('http://localhost:8765/cb', SECRET);
  assert.equal(verifyState(signed, 'short'), null);
});
