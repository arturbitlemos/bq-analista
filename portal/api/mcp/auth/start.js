const { signState } = require('../_helpers/state');

const PORT_MIN = 8765;
const PORT_MAX = 8799;
const NONCE_RE = /^[A-Za-z0-9_-]{8,64}$/;

function isValidLoopback(uri) {
  try {
    const u = new URL(uri);
    if (u.protocol !== 'http:') return false;
    if (u.hostname !== 'localhost' && u.hostname !== '127.0.0.1') return false;
    const port = parseInt(u.port, 10);
    if (!(port >= PORT_MIN && port <= PORT_MAX)) return false;
    return true;
  } catch {
    return false;
  }
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).send('Method not allowed');
  }
  const redirectUri = (req.query && req.query.redirect_uri) || '';
  if (!isValidLoopback(redirectUri)) {
    return res.status(400).send('redirect_uri inválido (deve ser http://localhost:PORT/cb com PORT ∈ [8765, 8799])');
  }

  const nonce = (req.query && req.query.nonce) || '';
  if (!NONCE_RE.test(nonce)) {
    return res.status(400).send('nonce inválido (deve ser base64url, 8-64 chars)');
  }

  const { AZURE_CLIENT_ID, AZURE_TENANT_ID, SESSION_SECRET } = process.env;
  if (!AZURE_CLIENT_ID || !AZURE_TENANT_ID || !SESSION_SECRET) {
    return res.status(500).send('Variáveis de ambiente não configuradas');
  }

  const state = signState(redirectUri, nonce, SESSION_SECRET);

  const cookie = [
    `mcp_oauth_state=${state}`,
    'Path=/api/mcp/auth',
    'HttpOnly',
    'Secure',
    'SameSite=Lax',
    'Max-Age=600',
  ].join('; ');
  res.setHeader('Set-Cookie', cookie);

  const callbackUri = `https://${req.headers.host}/api/mcp/auth/callback`;
  const authorize = new URL(`https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/authorize`);
  authorize.searchParams.set('client_id', AZURE_CLIENT_ID);
  authorize.searchParams.set('response_type', 'code');
  authorize.searchParams.set('redirect_uri', callbackUri);
  authorize.searchParams.set('response_mode', 'query');
  authorize.searchParams.set('scope', 'openid profile email');
  authorize.searchParams.set('state', state);

  res.setHeader('Location', authorize.toString());
  return res.status(302).end();
};
