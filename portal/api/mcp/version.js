const { VERSION, SKILL_VERSION } = require('./_helpers/manifest');

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');
  res.setHeader('Cache-Control', 'public, max-age=60');
  return res.status(200).json({ ...VERSION, skill: SKILL_VERSION.latest });
};
