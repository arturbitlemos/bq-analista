const { SKILL_VERSION } = require('./mcp/_helpers/manifest');

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');
  res.setHeader('Location', `/public/downloads/azzas-analista-${SKILL_VERSION.latest}.zip`);
  return res.status(302).end();
};
