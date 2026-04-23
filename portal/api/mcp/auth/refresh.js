const { refreshAccess } = require('../_helpers/jwt');

const ACCESS_TTL_S = 1800;

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).send('Method not allowed');

  const auth = req.headers.authorization || '';
  const match = auth.match(/^Bearer\s+(.+)$/);
  if (!match) return res.status(401).json({ error: 'bearer token ausente' });

  const { MCP_JWT_SECRET } = process.env;
  const MCP_JWT_ISSUER = process.env.MCP_JWT_ISSUER || 'mcp-exec-azzas';
  if (!MCP_JWT_SECRET) return res.status(500).json({ error: 'env não configurada' });

  try {
    const access = refreshAccess(match[1], MCP_JWT_SECRET, MCP_JWT_ISSUER, ACCESS_TTL_S);
    const exp = Math.floor(Date.now() / 1000) + ACCESS_TTL_S;
    return res.status(200).json({ access, access_exp: exp });
  } catch (err) {
    return res.status(401).json({ error: 'refresh inválido', detail: String(err && err.message || err) });
  }
};
