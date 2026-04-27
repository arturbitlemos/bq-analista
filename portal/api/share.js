const { getSql } = require('./_helpers/db')
const { verifySession } = require('./_helpers/session')
const { parseCookie } = require('./_helpers/cookie')
const { normalizeEmail } = require('./_helpers/email')

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const { id, public: makePublic, shared_with: rawShared } = req.body || {}
  if (!id) return res.status(400).json({ error: 'id required' })
  if (typeof makePublic !== 'boolean') return res.status(400).json({ error: 'public must be boolean' })

  let normalizedShared = []
  try {
    normalizedShared = (Array.isArray(rawShared) ? rawShared : []).map(normalizeEmail)
  } catch (e) {
    return res.status(400).json({ error: `invalid email: ${e.message}` })
  }

  const sql = getSql()
  const rows = await sql`SELECT author_email, public, shared_with FROM analyses WHERE id = ${id} LIMIT 1`
  if (rows.length === 0) return res.status(404).json({ error: 'not found' })
  const row = rows[0]
  if (row.author_email !== email) return res.status(403).json({ error: 'only author can change acl' })

  const before = { public: row.public, shared_with: row.shared_with || [] }
  const added = normalizedShared.filter(e => !before.shared_with.includes(e))
  const removed = before.shared_with.filter(e => !normalizedShared.includes(e))

  const metadata = JSON.stringify({
    before,
    after: { public: makePublic, shared_with: normalizedShared },
    added,
    removed,
  })

  await sql.transaction([
    sql`UPDATE analyses SET public = ${makePublic}, shared_with = ${normalizedShared}, updated_at = NOW() WHERE id = ${id}`,
    sql`INSERT INTO audit_log (action, actor_email, analysis_id, metadata) VALUES ('share', ${email}, ${id}, ${metadata}::jsonb)`,
  ])

  return res.status(200).json({ ok: true, public: makePublic, shared_with: normalizedShared })
}
