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
  const url = new URL(request.url)
  const pathname = decodeURIComponent(url.pathname)
  const isOnboarding = pathname === '/onboarding' || pathname === '/onboarding/'

  const redirectToLogin = () => {
    const loginUrl = new URL('/', url)
    loginUrl.searchParams.set('next', pathname)
    return Response.redirect(loginUrl.toString(), 302)
  }

  if (!sessionCookie) {
    if (isOnboarding) return redirectToLogin()
    return new Response('Não autenticado', { status: 401 })
  }

  const sessionIdentity = await verifySession(sessionCookie, process.env.SESSION_SECRET)
  if (!sessionIdentity) {
    if (isOnboarding) return redirectToLogin()
    return new Response('Sessão inválida ou expirada', { status: 401 })
  }

  if (isOnboarding) return;

  // /library/{domain}/{filename}.json
  if (pathname.startsWith('/library/')) {
    const filename = pathname.split('/').pop() // e.g. "user@corp.com.json" or "public.json"
    const fileIdentity = filename.replace(/\.json$/, '')
    if (fileIdentity === 'public') return // qualquer autenticado: deixa passar
    if (fileIdentity !== sessionIdentity) return new Response('Acesso negado', { status: 403 })
    return // identidade bate: deixa passar
  }

  // /analyses/* — aceita legado (3 seg) e novo (4 seg):
  //   legado:  /analyses/{public|identity}/{filename}            → identity em parts[1]
  //   novo:    /analyses/{domain}/{public|identity}/{filename}   → identity em parts[2]
  const parts = pathname.split('/').filter(Boolean)
  let identitySegment
  if (parts.length === 3) identitySegment = parts[1]
  else if (parts.length === 4) identitySegment = parts[2]
  else return new Response('Not Found', { status: 404 })

  if (identitySegment === 'public') return
  if (identitySegment !== sessionIdentity) return new Response('Acesso negado', { status: 403 })
}

export const config = { matcher: ['/analyses/:path*', '/library/:path*', '/onboarding'] }
