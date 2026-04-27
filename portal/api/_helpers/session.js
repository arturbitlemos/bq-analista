const crypto = require('crypto')

/**
 * Verify the HMAC-signed session cookie issued by api/auth.js.
 *
 * Cookie format: `<identity>~<expiry>~<base64url(hmac_sha256(SESSION_SECRET, identity~expiry))>`.
 * Returns the identity (lowercased email) on success, null on tampering / expiry / bad input.
 *
 * Mirrors the SubtleCrypto-based verifier in middleware.js but uses Node crypto so it
 * works in default Node serverless functions without ECMAScript module gymnastics.
 */
function verifySession(cookieValue, secret) {
  if (!cookieValue || !secret) return null
  const parts = cookieValue.split('~')
  if (parts.length < 3) return null
  const signature = parts.pop()
  const expiry = parts.pop()
  const identity = parts.join('~')

  const expiryNum = parseInt(expiry, 10)
  if (Number.isNaN(expiryNum) || expiryNum < Math.floor(Date.now() / 1000)) return null

  const expected = crypto
    .createHmac('sha256', secret)
    .update(`${identity}~${expiry}`)
    .digest('base64url')

  // Constant-time comparison to avoid signature timing oracles.
  const expectedBuf = Buffer.from(expected)
  const actualBuf = Buffer.from(signature)
  if (expectedBuf.length !== actualBuf.length) return null
  if (!crypto.timingSafeEqual(expectedBuf, actualBuf)) return null

  return identity
}

module.exports = { verifySession }
