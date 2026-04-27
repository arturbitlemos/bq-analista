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
  const url = new URL(request.url)
  const pathname = decodeURIComponent(url.pathname)
  // Only /onboarding still needs middleware-level auth — `/library/*` and
  // `/analyses/*` static paths were retired with the Postgres+Blob migration
  // (Phase B). The /api/* endpoints enforce ACL themselves on the data they
  // serve, so middleware doesn't need to gate them.
  if (pathname !== '/onboarding' && pathname !== '/onboarding/') return

  const cookie = parseCookie(request.headers.get('cookie'), 'session')
  if (!cookie) {
    const loginUrl = new URL('/', url)
    loginUrl.searchParams.set('next', pathname)
    return Response.redirect(loginUrl.toString(), 302)
  }
  const identity = await verifySession(cookie, process.env.SESSION_SECRET)
  if (!identity) {
    const loginUrl = new URL('/', url)
    loginUrl.searchParams.set('next', pathname)
    return Response.redirect(loginUrl.toString(), 302)
  }
}

export const config = { matcher: ['/onboarding'] }
