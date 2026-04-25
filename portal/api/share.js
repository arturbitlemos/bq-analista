const crypto = require('crypto')
const { parseCookie } = require('./_helpers/cookie')

function verifySession(cookieValue, secret) {
  const parts = cookieValue.split('~')
  if (parts.length < 3) return null
  const signature = parts.pop()
  const expiry = parts.pop()
  const identity = parts.join('~')
  if (parseInt(expiry) < Date.now() / 1000) return null
  const expected = crypto.createHmac('sha256', secret).update(`${identity}~${expiry}`).digest('base64url')
  const a = Buffer.from(expected)
  const b = Buffer.from(signature)
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null
  return identity
}

function encodeGhPath(filePath) {
  return filePath.split('/').map(s => encodeURIComponent(s)).join('/')
}

function emailSlug(identity) {
  return identity.replace(/[^a-z0-9]/gi, '-').replace(/-+/g, '-').toLowerCase().slice(0, 24)
}

async function ghFetch(endpoint, options = {}) {
  const { GITHUB_TOKEN, GITHUB_REPO } = process.env
  const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}${endpoint}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw Object.assign(new Error(`GitHub ${endpoint}: ${res.status} ${text.slice(0, 200)}`), { status: res.status })
  }
  return res.json()
}

async function readFileBase64(filePath) {
  const data = await ghFetch(`/contents/${encodeGhPath(filePath)}`)
  return data.content.replace(/\n/g, '')
}

async function readFileJson(filePath) {
  const b64 = await readFileBase64(filePath)
  return JSON.parse(Buffer.from(b64, 'base64').toString('utf-8'))
}

function toBase64(str) {
  return Buffer.from(str, 'utf-8').toString('base64')
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' })

  // CSRF: reject cross-origin requests
  const origin = req.headers.origin ?? ''
  const host = (req.headers.host ?? '').split(':')[0]
  if (origin && !origin.includes(host)) {
    return res.status(403).json({ error: 'Origin inválido' })
  }

  const { SESSION_SECRET, GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH = 'main' } = process.env
  const domain = process.env.PORTAL_DOMAIN ?? 'vendas-linx'
  if (!SESSION_SECRET || !GITHUB_TOKEN || !GITHUB_REPO) {
    return res.status(500).json({ error: 'Variáveis de ambiente não configuradas' })
  }

  // Auth
  const sessionCookie = parseCookie(req.headers.cookie ?? '', 'session')
  if (!sessionCookie) return res.status(401).json({ error: 'Não autenticado' })
  const identity = verifySession(sessionCookie, SESSION_SECRET)
  if (!identity) return res.status(401).json({ error: 'Sessão inválida ou expirada' })

  const { analysisId } = req.body ?? {}
  if (!analysisId || typeof analysisId !== 'string' || analysisId.length > 200) {
    return res.status(400).json({ error: 'analysisId inválido' })
  }

  try {
    // 1. Read user's private library and find the entry
    const privateLibPath = `library/${domain}/${identity}.json`
    const privateLibrary = await readFileJson(privateLibPath)

    const entryIdx = privateLibrary.findIndex(e => e.id === analysisId)
    if (entryIdx === -1) return res.status(404).json({ error: 'Análise não encontrada' })

    const entry = privateLibrary[entryIdx]

    // Ownership: file must live under analyses/{domain}/{identity}/
    const expectedPrefix = `analyses/${domain}/${identity}/`
    if (!entry.file?.startsWith(expectedPrefix)) {
      return res.status(403).json({ error: 'Acesso negado' })
    }

    // Prefix public filename with email slug to avoid cross-user collisions
    const origFilename = entry.file.split('/').pop()
    const publicFilename = `${emailSlug(identity)}-${origFilename}`
    const publicFilePath = `analyses/${domain}/public/${publicFilename}`
    const publicLink = `/analyses/${domain}/public/${publicFilename}`

    if (entry.public) {
      return res.status(200).json({ alreadyPublic: true, publicUrl: publicLink })
    }

    // 2. Read HTML and public library in parallel
    const [htmlBase64, publicLibrary] = await Promise.all([
      readFileBase64(entry.file),
      readFileJson(`library/${domain}/public.json`).catch(err => {
        if (err.status === 404) return []
        throw err
      }),
    ])

    // 3. Build updated state
    const publicEntry = { ...entry, public: true, file: publicFilePath, link: publicLink }
    const newPublicLibrary = [publicEntry, ...publicLibrary.filter(e => e.id !== analysisId)]
    const newPrivateLibrary = privateLibrary.map((e, i) =>
      i === entryIdx ? { ...e, public: true } : e
    )

    // 4. Get current commit + base tree SHA
    const refData = await ghFetch(`/git/ref/heads/${GITHUB_BRANCH}`)
    const currentCommitSha = refData.object.sha
    const commitData = await ghFetch(`/git/commits/${currentCommitSha}`)
    const baseTreeSha = commitData.tree.sha

    // 5. Create blobs in parallel
    const [htmlBlob, publicLibBlob, privateLibBlob] = await Promise.all([
      ghFetch('/git/blobs', {
        method: 'POST',
        body: JSON.stringify({ content: htmlBase64, encoding: 'base64' }),
      }),
      ghFetch('/git/blobs', {
        method: 'POST',
        body: JSON.stringify({ content: toBase64(JSON.stringify(newPublicLibrary, null, 2)), encoding: 'base64' }),
      }),
      ghFetch('/git/blobs', {
        method: 'POST',
        body: JSON.stringify({ content: toBase64(JSON.stringify(newPrivateLibrary, null, 2)), encoding: 'base64' }),
      }),
    ])

    // 6. Atomic tree: all 3 files in one commit
    const tree = await ghFetch('/git/trees', {
      method: 'POST',
      body: JSON.stringify({
        base_tree: baseTreeSha,
        tree: [
          { path: publicFilePath, mode: '100644', type: 'blob', sha: htmlBlob.sha },
          { path: `library/${domain}/public.json`, mode: '100644', type: 'blob', sha: publicLibBlob.sha },
          { path: privateLibPath, mode: '100644', type: 'blob', sha: privateLibBlob.sha },
        ],
      }),
    })

    // 7. Create commit
    const safeTitle = entry.title.replace(/[\r\n]/g, ' ')
    const commit = await ghFetch('/git/commits', {
      method: 'POST',
      body: JSON.stringify({
        message: `publish: ${safeTitle} → público`,
        tree: tree.sha,
        parents: [currentCommitSha],
      }),
    })

    // 8. Advance branch ref — 422 means a concurrent write landed first
    try {
      await ghFetch(`/git/refs/heads/${GITHUB_BRANCH}`, {
        method: 'PATCH',
        body: JSON.stringify({ sha: commit.sha }),
      })
    } catch (err) {
      if (err.status === 422) {
        return res.status(409).json({ error: 'Conflito de edição simultânea — tente novamente.' })
      }
      throw err
    }

    return res.status(200).json({ publicUrl: publicLink, commitSha: commit.sha })
  } catch (err) {
    console.error('share error:', err)
    return res.status(500).json({ error: err.message })
  }
}
