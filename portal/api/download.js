const { VERSION, SKILL_VERSION } = require('./mcp/_helpers/manifest');

// Single function for both DXT and Skill downloads. The legacy URLs
// /api/download-dxt and /api/download-skill are mapped here via vercel.json
// rewrites so external links (DXT manifest, README, bookmarks) keep working.
const TYPES = {
  dxt: () => `/public/downloads/azzas-mcp-${VERSION.latest}.dxt`,
  skill: () => `/public/downloads/azzas-analista-${SKILL_VERSION.latest}.zip`,
};

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');
  const type = (req.query?.type || '').toString();
  const buildLocation = TYPES[type];
  if (!buildLocation) return res.status(400).send(`unknown download type: ${type}`);
  res.setHeader('Location', buildLocation());
  return res.status(302).end();
};
