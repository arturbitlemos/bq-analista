const jwt = require('jsonwebtoken');

const MIN_SECRET_BYTES = 32;

function checkSecret(secret) {
  if (Buffer.byteLength(secret, 'utf8') < MIN_SECRET_BYTES) {
    throw new Error(`JWT secret must be at least ${MIN_SECRET_BYTES} bytes for HS256`);
  }
}

function encode(kind, { email, secret, issuer, ttl }) {
  const now = Math.floor(Date.now() / 1000);
  const exp = now + ttl;
  const payload = { iss: issuer, sub: email, email, kind, iat: now, exp };
  const token = jwt.sign(payload, secret, { algorithm: 'HS256', noTimestamp: true });
  return { token, exp };
}

function issueTokens({ email, secret, issuer, accessTtlS, refreshTtlS }) {
  checkSecret(secret);
  const a = encode('access', { email, secret, issuer, ttl: accessTtlS });
  const r = encode('refresh', { email, secret, issuer, ttl: refreshTtlS });
  return { access: a.token, refresh: r.token, accessExp: a.exp, refreshExp: r.exp };
}

function decodeToken(token, secret, issuer) {
  checkSecret(secret);
  return jwt.verify(token, secret, { algorithms: ['HS256'], issuer });
}

function refreshAccess(refreshToken, secret, issuer, accessTtlS) {
  const claims = decodeToken(refreshToken, secret, issuer);
  if (claims.kind !== 'refresh') throw new Error('not a refresh token');
  return encode('access', { email: claims.email, secret, issuer, ttl: accessTtlS });
}

module.exports = { issueTokens, decodeToken, refreshAccess };
