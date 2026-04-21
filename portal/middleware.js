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
  if (parts.length < 3) return null
  const signature = parts.pop()
  const expiry = parts.pop()
  const identity = parts.join('~')

  if (parseInt(expiry) < Date.now() / 1000) return null

  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify']
  )
  const data = new TextEncoder().encode(`${identity}~${expiry}`)
  const sigBytes = b64urlToBytes(signature)
  const valid = await crypto.subtle.verify('HMAC', key, sigBytes, data)

  return valid ? identity : null
}

export default async function middleware(request) {
  const cookieHeader = request.headers.get('cookie')
  const sessionCookie = parseCookie(cookieHeader, 'session')

  if (!sessionCookie) {
    return new Response('Não autenticado', { status: 401 })
  }

  const sessionIdentity = await verifySession(sessionCookie, process.env.SESSION_SECRET)
  if (!sessionIdentity) {
    return new Response('Sessão inválida ou expirada', { status: 401 })
  }

  const url = new URL(request.url)
  const pathname = decodeURIComponent(url.pathname)

  // Proteção de /library/{domain}/{identity}.json
  if (pathname.startsWith('/library/')) {
    const filename = pathname.split('/').pop() // e.g. "user@corp.com.json" or "public.json"
    const fileIdentity = filename.replace(/\.json$/, '')
    if (fileIdentity === 'public') return // qualquer autenticado: deixa passar
    if (fileIdentity !== sessionIdentity) return new Response('Acesso negado', { status: 403 })
    return // identidade bate: deixa passar
  }

  // url.pathname = /analyses/{domain}/{identity}/{filename}
  const parts = pathname.split('/')
  const segment = parts[3] // [0]='' [1]='analyses' [2]=domain [3]=identity

  if (!segment) return new Response('Not Found', { status: 404 })
  if (segment === 'public') return // qualquer autenticado: deixa passar
  if (segment !== sessionIdentity) return new Response('Acesso negado', { status: 403 })
  // identidade bate: deixa passar
}

export const config = { matcher: ['/analyses/:path*', '/library/:path*'] }
