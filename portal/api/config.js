export default async (req, res) => {
  res.setHeader('Content-Type', 'application/json')

  if (!process.env.AZURE_CLIENT_ID || !process.env.AZURE_TENANT_ID) {
    return res.status(500).json({ error: 'Missing Azure configuration' })
  }

  res.status(200).json({
    clientId: process.env.AZURE_CLIENT_ID,
    tenantId: process.env.AZURE_TENANT_ID,
    domain: process.env.PORTAL_DOMAIN ?? 'vendas-linx'
  })
}
