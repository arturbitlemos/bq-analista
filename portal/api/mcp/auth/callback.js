const { verifyState } = require('../_helpers/state');
const { issueTokens } = require('../_helpers/jwt');

const ACCESS_TTL_S = 1800;
const REFRESH_TTL_S = 604800;

function parseCookie(header, name) {
  if (!header) return null;
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return v.join('=');
  }
  return null;
}

function b64urlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  while (str.length % 4) str += '=';
  return Buffer.from(str, 'base64').toString('utf8');
}

function decodeIdToken(idToken) {
  const parts = idToken.split('.');
  if (parts.length !== 3) throw new Error('bad id_token');
  return JSON.parse(b64urlDecode(parts[1]));
}

function redirectLoopback(res, redirectUri, params) {
  const u = new URL(redirectUri);
  for (const [k, v] of Object.entries(params)) {
    u.searchParams.set(k, String(v));
  }
  res.setHeader('Location', u.toString());
  return res.status(302).end();
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');

  const { AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET, SESSION_SECRET, MCP_JWT_SECRET } = process.env;
  const MCP_JWT_ISSUER = process.env.MCP_JWT_ISSUER || 'azzas-mcp';
  if (!AZURE_CLIENT_ID || !AZURE_TENANT_ID || !AZURE_CLIENT_SECRET || !SESSION_SECRET || !MCP_JWT_SECRET) {
    return res.status(500).send('Variáveis de ambiente não configuradas');
  }

  const stateCookie = parseCookie(req.headers.cookie, 'mcp_oauth_state');
  if (!stateCookie) return res.status(400).send('state cookie ausente');
  const stateResult = verifyState(stateCookie, SESSION_SECRET);
  if (!stateResult) return res.status(400).send('state inválido ou expirado');

  const { redirectUri } = stateResult;
  const { code } = req.query ?? {};
  if (!code) return redirectLoopback(res, redirectUri, { error: 'invalid_code', error_description: 'code ausente' });

  const callbackUri = `https://${req.headers.host}/api/mcp/auth/callback`;
  const body = new URLSearchParams({
    client_id: AZURE_CLIENT_ID,
    client_secret: AZURE_CLIENT_SECRET,
    grant_type: 'authorization_code',
    code,
    redirect_uri: callbackUri,
  });

  let tokenRes;
  try {
    tokenRes = await fetch(`https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
  } catch {
    return redirectLoopback(res, redirectUri, { error: 'azure_error', error_description: 'rede' });
  }
  if (!tokenRes.ok) {
    return redirectLoopback(res, redirectUri, { error: 'invalid_code', error_description: 'troca de code falhou' });
  }
  const tokenBody = await tokenRes.json();
  let claims;
  try {
    claims = decodeIdToken(tokenBody.id_token);
  } catch {
    return redirectLoopback(res, redirectUri, { error: 'azure_error', error_description: 'id_token malformado' });
  }
  if (claims.tid !== AZURE_TENANT_ID) {
    return redirectLoopback(res, redirectUri, { error: 'wrong_tenant' });
  }
  const email = (claims.preferred_username || claims.email || '').toLowerCase().trim();
  if (!email) return redirectLoopback(res, redirectUri, { error: 'azure_error', error_description: 'email ausente' });

  const pair = issueTokens({
    email,
    secret: MCP_JWT_SECRET,
    issuer: MCP_JWT_ISSUER,
    accessTtlS: ACCESS_TTL_S,
    refreshTtlS: REFRESH_TTL_S,
  });

  res.setHeader('Set-Cookie', 'mcp_oauth_state=; Path=/api/mcp/auth; HttpOnly; Secure; SameSite=Lax; Max-Age=0');
  return redirectLoopback(res, redirectUri, {
    access: pair.access,
    refresh: pair.refresh,
    access_exp: pair.accessExp,
    refresh_exp: pair.refreshExp,
    email,
  });
};
