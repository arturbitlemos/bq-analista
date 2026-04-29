const { verifySession } = require('./_helpers/session')
const { parseCookie } = require('./_helpers/cookie')
const { mintProxyJwt } = require('./_helpers/proxy_jwt')

const AGENT_URLS = {
  'vendas-linx': process.env.AGENT_VENDAS_LINX_URL,
  'devolucoes':  process.env.AGENT_DEVOLUCOES_URL,
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const { agent, id, start_date, end_date } = req.body || {}
  if (!agent || !id || !start_date || !end_date) {
    return res.status(400).json({ error: 'agent, id, start_date, end_date required' })
  }
  const baseUrl = AGENT_URLS[agent]
  if (!baseUrl) return res.status(400).json({ error: `unknown agent: ${agent}` })

  const token = mintProxyJwt(email, 60)
  const targetUrl = `${baseUrl}/api/refresh/${encodeURIComponent(id)}`
  const headers = {
    authorization: `Bearer ${token}`,
    'content-type': 'application/json',
  }
  const body = JSON.stringify({ start_date, end_date })

  // 1 retry with short backoff to cover Railway cold starts (~2s).
  // Don't retry on >= 400 responses — those are deterministic business answers.
  async function callOnce() {
    return await fetch(targetUrl, { method: 'POST', headers, body })
  }

  let upstream
  try {
    upstream = await callOnce()
  } catch (e) {
    await new Promise(r => setTimeout(r, 2000))
    try {
      upstream = await callOnce()
    } catch (e2) {
      return res.status(503).json({ error: `agent unreachable: ${e2.message}` })
    }
  }

  const text = await upstream.text()
  res
    .status(upstream.status)
    .setHeader('content-type', upstream.headers.get('content-type') || 'application/json')
    .send(text)
}
