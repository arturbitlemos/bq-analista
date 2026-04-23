const { VERSION } = require('./mcp/_helpers/manifest');

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');
  res.setHeader('Location', `/downloads/azzas-mcp-${VERSION.latest}.dxt`);
  return res.status(302).end();
};
