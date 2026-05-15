import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function loadSecret() {
  const envPath = path.resolve(__dirname, '../../portal/.env.local')
  const txt = fs.readFileSync(envPath, 'utf8')
  const m = txt.match(/^SESSION_SECRET="?([^"\n]+)"?$/m)
  if (!m) throw new Error('SESSION_SECRET not found in portal/.env.local')
  return m[1]
}

export function mintSessionCookie(identity, { ttlHours = 8 } = {}) {
  const secret = loadSecret()
  const expiry = Math.floor(Date.now() / 1000) + ttlHours * 3600
  const payload = `${identity}~${expiry}`
  const hmac = crypto.createHmac('sha256', secret).update(payload).digest('base64url')
  return `${payload}~${hmac}`
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const identity = process.argv[2] || 'artur.lemos@somagrupo.com.br'
  console.log(mintSessionCookie(identity))
}
