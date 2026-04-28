const jwt = require('jsonwebtoken')

/**
 * Mint a short-lived HS256 JWT for proxying authenticated portal requests
 * to the mcp-core Railway service. Audience: 'mcp-core-proxy'.
 * Default TTL: 60s (long enough for one upstream RPC, short enough that a
 * leaked token expires quickly).
 */
function mintProxyJwt(email, ttlSeconds = 60) {
  const secret = process.env.MCP_PROXY_SIGNING_KEY
  if (!secret) throw new Error('MCP_PROXY_SIGNING_KEY not set')
  return jwt.sign(
    { email, aud: 'mcp-core-proxy' },
    secret,
    { algorithm: 'HS256', expiresIn: ttlSeconds },
  )
}

module.exports = { mintProxyJwt }
