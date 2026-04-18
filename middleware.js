function parseCookie(header, name) {
  if (!header) return null
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k === name) return v.join('=')
  }
  return null
}

function b64urlToBytes(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/')
  while (str.length % 4) str += '='
  return Uint8Array.from(atob(str), c => c.charCodeAt(0))
}

async function verifySession(cookieValue, secret) {
  const parts = cookieValue.split('~')
  if (parts.length !== 3) return null
  const [oid, expiry, signature] = parts

  if (parseInt(expiry) < Date.now() / 1000) return null

  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify']
  )
  const data = new TextEncoder().encode(`${oid}~${expiry}`)
  const sigBytes = b64urlToBytes(signature)
  const valid = await crypto.subtle.verify('HMAC', key, sigBytes, data)

  return valid ? oid : null
}

export default async function middleware(request) {
  const cookieHeader = request.headers.get('cookie')
  const sessionCookie = parseCookie(cookieHeader, 'session')

  if (!sessionCookie) {
    return new Response('Não autenticado', { status: 401 })
  }

  const sessionOid = await verifySession(sessionCookie, process.env.SESSION_SECRET)
  if (!sessionOid) {
    return new Response('Sessão inválida ou expirada', { status: 401 })
  }

  const url = new URL(request.url)
  const { pathname } = url

  // Proteção de /library/{oid}.json
  if (pathname.startsWith('/library/')) {
    const filename = pathname.slice('/library/'.length) // e.g. "abc123.json" or "public.json"
    const fileOid = filename.replace(/\.json$/, '')
    if (fileOid === 'public') return // qualquer autenticado: deixa passar
    if (fileOid !== sessionOid) return new Response('Acesso negado', { status: 403 })
    return // OID bate: deixa passar
  }

  // url.pathname = /analyses/public/... ou /analyses/{oid}/...
  const segment = pathname.split('/')[2]

  if (!segment) return new Response('Not Found', { status: 404 })
  if (segment === 'public') return // qualquer autenticado: deixa passar
  if (segment !== sessionOid) return new Response('Acesso negado', { status: 403 })
  // OID bate: deixa passar
}

export const config = { matcher: ['/analyses/:path*', '/library/:path*'] }
