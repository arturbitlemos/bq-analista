const { test } = require('node:test');
const assert = require('node:assert/strict');
const { isAdmin } = require('../adminAuth');

test('retorna true para email exato na lista', () => {
  const result = isAdmin('admin@soma.com', 'admin@soma.com');
  assert.equal(result, true);
});

test('retorna true case-insensitive', () => {
  const result = isAdmin('ADMIN@SOMA.COM', 'admin@soma.com');
  assert.equal(result, true);
});

test('retorna true com espaços ao redor do email na lista', () => {
  const result = isAdmin('admin@soma.com', '  admin@soma.com  ');
  assert.equal(result, true);
});

test('retorna false para email fora da lista', () => {
  const result = isAdmin('user@example.com', 'admin@soma.com,support@soma.com');
  assert.equal(result, false);
});

test('retorna false se adminEmailsEnv é string vazia', () => {
  const result = isAdmin('admin@soma.com', '');
  assert.equal(result, false);
});

test('retorna false se adminEmailsEnv é undefined', () => {
  const result = isAdmin('admin@soma.com', undefined);
  assert.equal(result, false);
});

test('retorna false se email é string vazia', () => {
  const result = isAdmin('', 'admin@soma.com');
  assert.equal(result, false);
});

test('ignora entradas vazias após split (vírgulas consecutivas)', () => {
  const result = isAdmin('admin@soma.com', 'admin@soma.com,,support@soma.com');
  assert.equal(result, true);
});
