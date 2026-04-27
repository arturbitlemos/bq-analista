// portal/api/internal/blob.js
const { put, head, del } = require('@vercel/blob')
const jwt = require('jsonwebtoken')

function verifyInternalJwt(authHeader) {
  if (!authHeader?.startsWith('Bearer ')) throw new Error('missing bearer')
  const token = authHeader.slice(7)
  return jwt.verify(token, process.env.MCP_PROXY_SIGNING_KEY, {
    algorithms: ['HS256'],
    audience: 'blob-internal',
  })
}

const config = { api: { bodyParser: false } }

async function readBody(req) {
  // Production path: stream is intact (bodyParser:false honored).
  if (!req.readableEnded) {
    const chunks = []
    for await (const chunk of req) chunks.push(chunk)
    return Buffer.concat(chunks)
  }
  // Local-dev fallback: `vercel dev` pre-parses the body and exposes it on
  // req.body even when `bodyParser:false` is set. Reconstitute a Buffer so
  // smoke tests pass against the local emulator.
  const b = req.body
  if (b == null) return Buffer.alloc(0)
  if (Buffer.isBuffer(b)) return b
  if (typeof b === 'string') return Buffer.from(b, 'utf8')
  return Buffer.from(JSON.stringify(b), 'utf8')
}

async function handler(req, res) {
  try {
    verifyInternalJwt(req.headers.authorization)
  } catch (e) {
    return res.status(401).json({ error: `unauthorized: ${e.message}` })
  }

  const pathname = (req.query?.pathname || '').toString()
  if (!pathname.startsWith('analyses/')) {
    return res.status(400).json({ error: 'pathname must start with analyses/' })
  }

  if (req.method === 'PUT') {
    const body = await readBody(req)
    const contentType = (req.query?.content_type || 'application/octet-stream').toString()
    const blob = await put(pathname, body, {
      access: 'public',
      contentType,
      allowOverwrite: true,
      addRandomSuffix: false,
    })
    return res.status(200).json({ url: blob.url, pathname: blob.pathname })
  }

  if (req.method === 'GET') {
    const info = await head(pathname).catch(() => null)
    if (!info) return res.status(404).json({ error: 'not found' })
    const dl = await fetch(info.url)
    if (!dl.ok) return res.status(502).json({ error: `blob fetch failed: ${dl.status}` })
    res.setHeader('content-type', info.contentType || 'application/octet-stream')
    res.setHeader('cache-control', 'private, no-store')
    res.send(Buffer.from(await dl.arrayBuffer()))
    return
  }

  if (req.method === 'DELETE') {
    await del(pathname)
    return res.status(204).end()
  }

  return res.status(405).json({ error: 'method not allowed' })
}

module.exports = handler
module.exports.config = config
module.exports.default = handler
