const crypto = require('crypto')

// Module-level JWKS cache (survives warm Lambda invocations)
let jwksCache = { keys: [], fetchedAt: 0 }
const JWKS_TTL_MS = 3_600_000

async function getJwks(tenantId) {
  if (Date.now() - jwksCache.fetchedAt < JWKS_TTL_MS) return jwksCache.keys
  const res = await fetch(
    `https://login.microsoftonline.com/${tenantId}/discovery/v2.0/keys`
  )
  const data = await res.json()
  jwksCache = { keys: data.keys, fetchedAt: Date.now() }
  return jwksCache.keys
}

function b64urlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/')
  while (str.length % 4) str += '='
  return Buffer.from(str, 'base64')
}

async function validateToken(token, clientId, tenantId) {
  const parts = token.split('.')
  if (parts.length !== 3) throw new Error('Formato de token inválido')

  const header = JSON.parse(b64urlDecode(parts[0]).toString())
  const payload = JSON.parse(b64urlDecode(parts[1]).toString())

  const now = Math.floor(Date.now() / 1000)
  const SKEW = 300
  if (payload.exp + SKEW < now) throw new Error('Token expirado')
  if (payload.nbf && payload.nbf - SKEW > now) throw new Error('Token ainda não válido')
  if (payload.aud !== clientId) throw new Error('Audience inválido')
  const validIssuer = `https://login.microsoftonline.com/${tenantId}/v2.0`
  if (payload.iss !== validIssuer) throw new Error('Issuer inválido')
  const identity = (payload.preferred_username || payload.email || '').toLowerCase().trim()
  if (!identity) throw new Error('Claim preferred_username/email ausente')

  const keys = await getJwks(tenantId)
  let jwk = keys.find(k => k.kid === header.kid)
  if (!jwk) {
    jwksCache.fetchedAt = 0  // force refresh
    const fresh = await getJwks(tenantId)
    jwk = fresh.find(k => k.kid === header.kid)
    if (!jwk) throw new Error('Chave de assinatura desconhecida')
  }

  const publicKey = crypto.createPublicKey({ key: jwk, format: 'jwk' })
  const data = Buffer.from(`${parts[0]}.${parts[1]}`)
  const signature = b64urlDecode(parts[2])
  const valid = crypto.verify('RSA-SHA256', data, publicKey, signature)
  if (!valid) throw new Error('Assinatura inválida')

  return identity
}

function createSessionCookie(identity, secret) {
  const expiry = Math.floor(Date.now() / 1000) + 8 * 3600
  const payload = `${identity}~${expiry}`
  const hmac = crypto.createHmac('sha256', secret).update(payload).digest('base64url')
  return `${payload}~${hmac}`
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const { idToken } = req.body ?? {}
  if (!idToken) return res.status(400).json({ error: 'idToken ausente' })

  const { AZURE_CLIENT_ID, AZURE_TENANT_ID, SESSION_SECRET } = process.env
  if (!AZURE_CLIENT_ID || !AZURE_TENANT_ID || !SESSION_SECRET) {
    return res.status(500).json({ error: 'Variáveis de ambiente não configuradas' })
  }

  try {
    const identity = await validateToken(idToken, AZURE_CLIENT_ID, AZURE_TENANT_ID)
    const cookieValue = createSessionCookie(identity, SESSION_SECRET)
    res.setHeader('Set-Cookie',
      `session=${cookieValue}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=28800`
    )
    res.status(200).json({ identity })
  } catch (err) {
    res.status(401).json({ error: err.message })
  }
}
