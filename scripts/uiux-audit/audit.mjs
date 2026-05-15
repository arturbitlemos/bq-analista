import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mintSessionCookie } from './cookie.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHOT_DIR = path.join(__dirname, 'screenshots')
const FINDINGS_DIR = path.join(__dirname, 'findings')
const BASE = process.env.BASE_URL || 'http://localhost:3001'
const USER = process.env.AUDIT_USER || 'artur.lemos@somagrupo.com.br'
const TAG = process.env.AUDIT_TAG || 'pre'

const VIEWPORTS = {
  desktop: { width: 1440, height: 900, deviceScaleFactor: 1 },
  mobile: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
}

const PAGES = [
  { id: 'home-logged-out', path: '/', auth: false, msal: false },
  { id: 'home-logged-in', path: '/', auth: true, msal: true, waitFor: '#library-view' },
  { id: 'onboarding', path: '/onboarding', auth: true, msal: false, waitFor: 'body' },
  { id: 'admin', path: '/admin', auth: true, msal: false, waitFor: 'body' },
  { id: 'dicionario', path: '/dicionario', auth: true, msal: false, waitFor: 'body' },
]

fs.mkdirSync(SHOT_DIR, { recursive: true })
fs.mkdirSync(FINDINGS_DIR, { recursive: true })

const FAKE_MSAL_MODULE = `
const account = { username: ${JSON.stringify(USER)}, name: ${JSON.stringify(USER)} };
const instance = {
  initialize: async () => {},
  handleRedirectPromise: async () => null,
  getAllAccounts: () => [account],
  acquireTokenSilent: async () => ({ idToken: 'stub-token', account }),
  loginRedirect: async () => {},
};
export async function initMsal() { return instance; }
export class InteractionRequiredAuthError extends Error {}
`

async function withContext(browser, viewport, auth) {
  const ctx = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: viewport.deviceScaleFactor,
    isMobile: !!viewport.isMobile,
    hasTouch: !!viewport.hasTouch,
    userAgent: viewport.isMobile
      ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
      : undefined,
  })
  if (auth) {
    const cookie = mintSessionCookie(USER)
    const url = new URL(BASE)
    await ctx.addCookies([{
      name: 'session', value: cookie, domain: url.hostname, path: '/',
      httpOnly: true, secure: false, sameSite: 'Lax',
    }])
  }
  return ctx
}

async function installMsalStub(ctx) {
  await ctx.route('**/msal-init.js', (route) =>
    route.fulfill({ status: 200, contentType: 'application/javascript', body: FAKE_MSAL_MODULE }))
  await ctx.route('**/api/auth', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ identity: USER }) }))
}

function attachObservers(page, store) {
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') store.console.push({ type: msg.type(), text: msg.text() })
  })
  page.on('pageerror', (err) => store.pageerrors.push(err.message))
  page.on('response', (resp) => { if (resp.status() >= 400) store.bad.push({ url: resp.url(), status: resp.status() }) })
  page.on('requestfailed', (req) => store.failed.push({ url: req.url(), reason: req.failure()?.errorText }))
}

async function visit(browser, page, viewport) {
  const vp = VIEWPORTS[viewport]
  const ctx = await withContext(browser, vp, page.auth)
  if (page.msal) await installMsalStub(ctx)
  const tab = await ctx.newPage()
  const store = { console: [], pageerrors: [], bad: [], failed: [] }
  attachObservers(tab, store)

  const start = Date.now()
  let navOk = true, navMs = 0
  try {
    const resp = await tab.goto(`${BASE}${page.path}`, { waitUntil: 'domcontentloaded', timeout: 25000 })
    navMs = Date.now() - start
    if (!resp || !resp.ok()) navOk = false
    if (page.waitFor) await tab.waitForSelector(page.waitFor, { timeout: 12000, state: 'visible' }).catch(() => {})
    await tab.waitForTimeout(2500)
  } catch (e) {
    navOk = false
    store.pageerrors.push(`navigation: ${e.message}`)
  }

  const shotPath = path.join(SHOT_DIR, `${TAG}.${page.id}.${viewport}.png`)
  await tab.screenshot({ path: shotPath, fullPage: true }).catch(() => {})

  let metrics = null
  try {
    metrics = await tab.evaluate(() => {
      const t = performance.getEntriesByType('navigation')[0]
      const paint = performance.getEntriesByType('paint')
      return {
        domContentLoaded: t ? Math.round(t.domContentLoadedEventEnd) : null,
        loadEvent: t ? Math.round(t.loadEventEnd) : null,
        firstContentfulPaint: Math.round(paint.find(p => p.name === 'first-contentful-paint')?.startTime || 0),
        resources: performance.getEntriesByType('resource').length,
      }
    })
  } catch {}

  await ctx.close()
  return {
    id: page.id, path: page.path, viewport, navOk, navMs,
    screenshot: path.relative(__dirname, shotPath),
    console: store.console.slice(0, 25), pageerrors: store.pageerrors.slice(0, 25),
    bad: store.bad.slice(0, 25), failed: store.failed.slice(0, 25), metrics,
  }
}

async function libraryDeepDive(browser) {
  const ctx = await withContext(browser, VIEWPORTS.desktop, true)
  await installMsalStub(ctx)
  const tab = await ctx.newPage()
  const store = { console: [], pageerrors: [], bad: [], failed: [] }
  attachObservers(tab, store)
  const f = { interactions: [] }

  await tab.goto(`${BASE}/`, { waitUntil: 'domcontentloaded', timeout: 25000 }).catch(() => {})
  await tab.waitForSelector('#library-view', { timeout: 12000, state: 'visible' }).catch(() => {})
  await tab.waitForTimeout(3000)

  const cardCount = await tab.locator('#grid > *').count().catch(() => 0)
  f.interactions.push({ step: 'card-count', value: cardCount })

  const tabs = await tab.locator('#library-view [role="tab"], .tab, [data-tab]').allInnerTexts().catch(() => [])
  f.interactions.push({ step: 'tabs', value: tabs })

  const searchSel = 'input[type="search"], input[placeholder*="usca" i], #search, input[placeholder*="search" i]'
  if (await tab.locator(searchSel).first().isVisible().catch(() => false)) {
    await tab.locator(searchSel).first().fill('venda')
    await tab.waitForTimeout(600)
    await tab.screenshot({ path: path.join(SHOT_DIR, `${TAG}.library-search.desktop.png`), fullPage: true })
    const after = await tab.locator('#grid > *').count().catch(() => 0)
    f.interactions.push({ step: 'search', ok: true, resultsAfter: after })
    await tab.locator(searchSel).first().fill('')
    await tab.waitForTimeout(400)
  } else {
    f.interactions.push({ step: 'search', ok: false, note: 'no search input' })
  }

  const firstCard = tab.locator('#grid > *').first()
  if (await firstCard.isVisible().catch(() => false)) {
    const clickStart = Date.now()
    await firstCard.click().catch(() => {})
    await tab.waitForTimeout(2500)
    f.interactions.push({ step: 'open-card', ok: true, ms: Date.now() - clickStart })
    await tab.screenshot({ path: path.join(SHOT_DIR, `${TAG}.analysis-open.desktop.png`), fullPage: true })
  } else {
    f.interactions.push({ step: 'open-card', ok: false, note: 'no card to click' })
  }

  f.console = store.console.slice(0, 30)
  f.pageerrors = store.pageerrors.slice(0, 30)
  f.bad = store.bad.slice(0, 30)
  f.failed = store.failed.slice(0, 30)
  await ctx.close()
  return f
}

async function launchBrowser() {
  try { return await chromium.launch({ headless: true }) }
  catch { return await chromium.launch({ headless: true, channel: 'chrome' }) }
}

async function main() {
  const cmd = process.argv[2] || 'discover'
  const browser = await launchBrowser()
  const out = { base: BASE, user: USER, tag: TAG, ts: new Date().toISOString(), pages: [], deep: null }
  const outPath = path.join(FINDINGS_DIR, `${TAG}.json`)

  try {
    for (const page of PAGES) {
      for (const viewport of Object.keys(VIEWPORTS)) {
        console.log(`→ ${page.id} (${viewport})`)
        out.pages.push(await visit(browser, page, viewport))
        fs.writeFileSync(outPath, JSON.stringify(out, null, 2))
      }
    }
    console.log('→ deep-dive library')
    out.deep = await libraryDeepDive(browser)
  } catch (e) {
    out.fatal = e.message
    console.error('non-fatal:', e.message)
  } finally {
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2))
    await browser.close()
  }
  console.log(`\nDone. ${out.pages.length} visits. Findings: ${outPath}`)
}

main().catch((e) => { console.error(e); process.exit(1) })
