const { getSql } = require('./_helpers/db')
const { verifySession } = require('./_helpers/session')
const { parseCookie } = require('./_helpers/cookie')

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const { id, archive } = req.body || {}
  if (!id || typeof archive !== 'boolean') {
    return res.status(400).json({ error: 'id + archive required' })
  }

  const sql = getSql()
  // ACL: user must be able to see the analysis to archive it for themselves
  const rows = await sql`
    SELECT 1 FROM analyses
    WHERE id = ${id}
      AND (author_email = ${email} OR public = TRUE OR ${email} = ANY(shared_with))
    LIMIT 1
  `
  if (rows.length === 0) return res.status(404).json({ error: 'not found or not accessible' })

  if (archive) {
    await sql`
      UPDATE analyses
      SET archived_by = array_append(array_remove(archived_by, ${email}), ${email}),
          updated_at = NOW()
      WHERE id = ${id}
    `
  } else {
    await sql`
      UPDATE analyses
      SET archived_by = array_remove(archived_by, ${email}),
          updated_at = NOW()
      WHERE id = ${id}
    `
  }
  await sql`
    INSERT INTO audit_log (action, actor_email, analysis_id)
    VALUES (${archive ? 'archive' : 'unarchive'}, ${email}, ${id})
  `
  return res.status(200).json({ ok: true })
}
