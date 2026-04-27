const { getSql } = require('../_helpers/db')
const { verifySession } = require('../_helpers/session')
const { parseCookie } = require('../_helpers/cookie')

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).end()

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).end('not authenticated')

  const id = (req.query?.id || '').toString()
  if (!id) return res.status(400).end('missing id')

  const sql = getSql()
  const rows = await sql`
    SELECT blob_url, author_email, public, shared_with
    FROM analyses
    WHERE id = ${id}
    LIMIT 1
  `
  if (rows.length === 0) return res.status(404).end('not found')

  const row = rows[0]
  const allowed = row.author_email === email || row.public || row.shared_with?.includes(email)
  if (!allowed) return res.status(403).end('forbidden')
  if (!row.blob_url) return res.status(500).end('blob_url not set (data integrity issue)')

  // Proxy the bytes server-side instead of redirecting to the public blob URL.
  // The blob URL is in a public Vercel Blob store and would otherwise be cached
  // in browser history / Referer / proxy logs, defeating the ACL above.
  const dl = await fetch(row.blob_url)
  if (!dl.ok) return res.status(502).end(`blob fetch failed: ${dl.status}`)

  res.setHeader('content-type', 'text/html; charset=utf-8')
  res.setHeader('cache-control', 'private, no-store')
  res.setHeader('x-content-type-options', 'nosniff')
  res.status(200).send(Buffer.from(await dl.arrayBuffer()))
}
