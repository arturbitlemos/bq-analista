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

  // Read current state for audit metadata diff. This SELECT can race with
  // concurrent writes; we accept that for the audit log's added/removed
  // accuracy. The actual write below is atomic and authorship-gated, which
  // is what the security model requires.
  const beforeRows = await sql`SELECT author_email, public, shared_with FROM analyses WHERE id = ${id} LIMIT 1`
  if (beforeRows.length === 0) return res.status(404).json({ error: 'not found' })
  const before = {
    public: beforeRows[0].public,
    shared_with: beforeRows[0].shared_with || [],
  }
  if (beforeRows[0].author_email !== email) return res.status(403).json({ error: 'only author can change acl' })

  const added = normalizedShared.filter(e => !before.shared_with.includes(e))
  const removed = before.shared_with.filter(e => !normalizedShared.includes(e))
  const metadata = JSON.stringify({
    before,
    after: { public: makePublic, shared_with: normalizedShared },
    added,
    removed,
  })

  // Atomic UPDATE+INSERT in a single statement, gated on author_email so
  // a concurrent writer who isn't the author can't slip in between read
  // and write. did_update tells us whether the guard matched.
  const result = await sql`
    WITH upd AS (
      UPDATE analyses
      SET public = ${makePublic}, shared_with = ${normalizedShared}, updated_at = NOW()
      WHERE id = ${id} AND author_email = ${email}
      RETURNING id
    ),
    aud AS (
      INSERT INTO audit_log (action, actor_email, analysis_id, metadata)
      SELECT 'share', ${email}, ${id}, ${metadata}::jsonb
      WHERE EXISTS (SELECT 1 FROM upd)
      RETURNING 1
    )
    SELECT EXISTS (SELECT 1 FROM upd) AS did_update
  `
  if (!result[0]?.did_update) {
    return res.status(403).json({ error: 'only author can change acl' })
  }

  return res.status(200).json({ ok: true, public: makePublic, shared_with: normalizedShared })
}
