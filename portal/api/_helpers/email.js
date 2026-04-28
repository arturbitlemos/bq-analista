function normalizeEmail(s) {
  if (!s || !s.trim()) throw new Error('empty email')
  const out = s.trim().toLowerCase()
  if (!out.includes('@')) throw new Error(`invalid email: missing @ in ${out}`)
  return out
}

module.exports = { normalizeEmail }
