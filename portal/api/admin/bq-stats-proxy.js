const { verifySession } = require('../_helpers/session')
const { parseCookie } = require('../_helpers/cookie')
const { isAdmin } = require('../_helpers/adminAuth')
const { mintProxyJwt } = require('../_helpers/proxy_jwt')

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })
  if (!isAdmin(email, process.env.ADMIN_EMAILS)) return res.status(403).json({ error: 'forbidden' })

  const mcpBase = process.env.MCP_BASE_URL
  if (!mcpBase) return res.status(503).json({ error: 'MCP_BASE_URL não configurado' })

  // mintProxyJwt reads MCP_PROXY_SIGNING_KEY from env automatically.
  // TTL of 60s is enough for one HTTP call.
  let token
  try {
    token = mintProxyJwt(email)
  } catch (err) {
    return res.status(503).json({ error: `JWT proxy: ${err.message}` })
  }

  let upstream
  try {
    upstream = await fetch(`${mcpBase}/api/admin/bq-stats`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10_000),
    })
  } catch (err) {
    return res.status(504).json({ error: `Railway indisponível: ${err.message}` })
  }

  if (!upstream.ok) {
    const text = await upstream.text().catch(() => upstream.statusText)
    return res.status(upstream.status).json({ error: text })
  }

  const data = await upstream.json()
  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json(data)
}
