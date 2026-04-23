const crypto = require('crypto');

const TTL_S = 600;

function signState(redirectUri, secret) {
  const nonce = crypto.randomBytes(16).toString('base64url');
  const exp = Math.floor(Date.now() / 1000) + TTL_S;
  const payload = `${nonce}~${exp}~${redirectUri}`;
  const hmac = crypto.createHmac('sha256', secret).update(payload).digest('base64url');
  return `${payload}~${hmac}`;
}

function verifyState(stateValue, secret) {
  const parts = stateValue.split('~');
  if (parts.length < 4) return null;
  const hmac = parts.pop();
  const payload = parts.join('~');
  const expected = crypto.createHmac('sha256', secret).update(payload).digest('base64url');
  if (hmac.length !== expected.length) return null;
  if (!crypto.timingSafeEqual(Buffer.from(hmac), Buffer.from(expected))) return null;
  const [, expStr, ...rest] = payload.split('~');
  const redirectUri = rest.join('~');
  if (parseInt(expStr, 10) < Math.floor(Date.now() / 1000)) return null;
  return { redirectUri };
}

module.exports = { signState, verifyState };
