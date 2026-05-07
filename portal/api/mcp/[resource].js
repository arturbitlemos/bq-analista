const { MANIFEST, VERSION, SKILL_VERSION } = require('./_helpers/manifest')

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed')
  res.setHeader('Cache-Control', 'public, max-age=60')

  const { resource } = req.query
  if (resource === 'agents') return res.status(200).json(MANIFEST)
  if (resource === 'version') return res.status(200).json({ ...VERSION, skill: SKILL_VERSION.latest })
  return res.status(404).json({ error: 'not found' })
}
