const { test } = require('node:test');
const assert = require('node:assert/strict');
const { signState, verifyState } = require('../_helpers/state');

const SECRET = 'z'.repeat(32);
const NONCE = 'abcdef12';

test('roundtrip state preserva redirectUri e clientNonce', () => {
  const signed = signState('http://localhost:8765/cb', NONCE, SECRET);
  const result = verifyState(signed, SECRET);
  assert.equal(result.redirectUri, 'http://localhost:8765/cb');
  assert.equal(result.clientNonce, NONCE);
});

test('tamper rejeitado', () => {
  const signed = signState('http://localhost:8765/cb', NONCE, SECRET);
  const tampered = signed.replace('8765', '9999');
  assert.equal(verifyState(tampered, SECRET), null);
});

test('secret errado rejeitado', () => {
  const signed = signState('http://localhost:8765/cb', NONCE, SECRET);
  assert.equal(verifyState(signed, 'y'.repeat(32)), null);
});

test('signState rejeita secret curto', () => {
  assert.throws(() => signState('http://localhost:8765/cb', NONCE, 'short'), /at least 32 bytes/);
});

test('verifyState retorna null com secret curto', () => {
  const signed = signState('http://localhost:8765/cb', NONCE, SECRET);
  assert.equal(verifyState(signed, 'short'), null);
});

test('signState rejeita clientNonce ausente', () => {
  assert.throws(() => signState('http://localhost:8765/cb', '', SECRET), /clientNonce required/);
  assert.throws(() => signState('http://localhost:8765/cb', null, SECRET), /clientNonce required/);
});

test('verifyState retorna null se state tem menos de 5 partes (corrompido)', () => {
  // Fewer than 5 tilde-separated parts
  const corrupted = 'part1~part2~part3~part4';
  assert.equal(verifyState(corrupted, SECRET), null);
});
