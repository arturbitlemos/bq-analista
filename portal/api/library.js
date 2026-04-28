const { getSql } = require('./_helpers/db')
const { verifySession } = require('./_helpers/session')
const { parseCookie } = require('./_helpers/cookie')

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const agent = (req.query?.agent || '').toString()
  if (!agent) return res.status(400).json({ error: 'agent param required' })

  const sql = getSql()
  const rows = await sql`
    SELECT id, agent_slug, author_email, title, brand, period_label, period_start, period_end,
           description, tags, public, shared_with, archived_by, last_refreshed_at,
           refresh_spec IS NOT NULL AS has_refresh_spec, created_at
    FROM analyses
    WHERE agent_slug = ${agent}
      AND (author_email = ${email} OR public = TRUE OR ${email} = ANY(shared_with))
    ORDER BY COALESCE(last_refreshed_at, created_at) DESC
  `

  const out = rows.map(r => {
    const isMine = r.author_email === email
    // PRIVACY: only the author sees the full shared_with list. Recipients only see
    // themselves in the list (so they can't deduce who else has access).
    const sharedWith = isMine
      ? (r.shared_with || [])
      : (r.shared_with?.includes(email) ? [email] : [])
    // PRIVACY: author_email is masked for recipients of a private share.
    // Authors and viewers of public analyses see it normally.
    const authorVisible = isMine || r.public
    const periodEnd = r.period_end ? new Date(r.period_end).toISOString().slice(0, 10) : null
    const createdDate = r.created_at ? new Date(r.created_at).toISOString().slice(0, 10) : null
    return {
      ...r,
      author_email: authorVisible ? r.author_email : null,
      shared_with: sharedWith,
      // Backward-compat aliases used by Fase A frontend code (period filter, card meta):
      date: periodEnd || createdDate,
      period: r.period_label,
      // Computed flags:
      is_mine: isMine,
      is_shared_with_me: r.shared_with?.includes(email) && !isMine && !r.public,
      is_archived: r.archived_by?.includes(email),
    }
  })

  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json({ items: out })
}
