const { test } = require('node:test')
const assert = require('node:assert/strict')
const { normalizeEmail } = require('../email')

test('lowercase', () => {
  assert.equal(normalizeEmail('Maria.Filo@Soma.com.br'), 'maria.filo@soma.com.br')
})

test('strip', () => {
  assert.equal(normalizeEmail('  a@b.com  '), 'a@b.com')
})

test('rejects empty', () => {
  assert.throws(() => normalizeEmail(''), /empty/)
  assert.throws(() => normalizeEmail('   '), /empty/)
})

test('rejects no-at', () => {
  assert.throws(() => normalizeEmail('notanemail'), /missing @/)
})
