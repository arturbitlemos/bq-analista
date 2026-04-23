const crypto = require('crypto');

const TTL_S = 600;
const MIN_SECRET_BYTES = 32;

function checkSecret(secret) {
  if (Buffer.byteLength(secret, 'utf8') < MIN_SECRET_BYTES) {
    throw new Error(`state secret must be at least ${MIN_SECRET_BYTES} bytes`);
  }
}

function signState(redirectUri, clientNonce, secret) {
  checkSecret(secret);
  if (!clientNonce || typeof clientNonce !== 'string') {
    throw new Error('clientNonce required');
  }
  const serverNonce = crypto.randomBytes(16).toString('base64url');
  const exp = Math.floor(Date.now() / 1000) + TTL_S;
  const payload = `${serverNonce}~${exp}~${clientNonce}~${redirectUri}`;
  const hmac = crypto.createHmac('sha256', secret).update(payload).digest('base64url');
  return `${payload}~${hmac}`;
}

function verifyState(stateValue, secret) {
  if (Buffer.byteLength(secret, 'utf8') < MIN_SECRET_BYTES) return null;
  const parts = stateValue.split('~');
  // serverNonce, exp, clientNonce, redirectUri..., hmac — min 5 parts
  if (parts.length < 5) return null;
  const hmac = parts.pop();
  const payload = parts.join('~');
  const expected = crypto.createHmac('sha256', secret).update(payload).digest('base64url');
  if (hmac.length !== expected.length) return null;
  if (!crypto.timingSafeEqual(Buffer.from(hmac), Buffer.from(expected))) return null;
  const [, expStr, clientNonce, ...rest] = payload.split('~');
  const redirectUri = rest.join('~');
  if (parseInt(expStr, 10) < Math.floor(Date.now() / 1000)) return null;
  return { redirectUri, clientNonce };
}

module.exports = { signState, verifyState };
