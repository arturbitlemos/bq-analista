// Captures the three rebuilt auth-shell states + the iframe loading overlay,
// which the normal sweep can't reach (they need specific MSAL/network conditions).
import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mintSessionCookie } from './cookie.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHOT = path.join(__dirname, 'screenshots')
const BASE = process.env.BASE_URL || 'http://localhost:3001'
const USER = 'artur.lemos@somagrupo.com.br'
const TAG = process.env.AUDIT_TAG || 'post'

const noAccountsMsal = `
const account = { username: ${JSON.stringify(USER)} };
const instance = {
  initialize: async () => {},
  handleRedirectPromise: async () => null,
  getAllAccounts: () => [],
  acquireTokenSilent: async () => { throw new Error('no account'); },
  loginRedirect: async () => { await new Promise(r => setTimeout(r, 99999)); },
};
export async function initMsal() { return instance; }
export class InteractionRequiredAuthError extends Error {}
`

async function launch() {
  try { return await chromium.launch({ headless: true }) }
  catch { return await chromium.launch({ headless: true, channel: 'chrome' }) }
}

async function shoot(browser, name, setup) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const cookie = mintSessionCookie(USER)
  await ctx.addCookies([{ name: 'session', value: cookie, domain: new URL(BASE).hostname, path: '/', sameSite: 'Lax' }])
  await setup(ctx)
  const tab = await ctx.newPage()
  await tab.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' }).catch(() => {})
  await tab.waitForTimeout(3500)
  await tab.screenshot({ path: path.join(SHOT, `${TAG}.${name}.desktop.png`), fullPage: true })
  await ctx.close()
  console.log(`✓ ${name}`)
}

async function main() {
  const browser = await launch()

  // 1. Branded sign-in screen (no MSAL account)
  await shoot(browser, 'state-signin', async (ctx) => {
    await ctx.route('**/msal-init.js', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: noAccountsMsal }))
  })

  // 2. Branded error screen (/api/config fails)
  await shoot(browser, 'state-error', async (ctx) => {
    await ctx.route('**/api/config', (r) => r.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"Missing Azure configuration"}' }))
  })

  // 3. Iframe loading overlay: open library, click a card, analysis hangs
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const cookie = mintSessionCookie(USER)
    await ctx.addCookies([{ name: 'session', value: cookie, domain: new URL(BASE).hostname, path: '/', sameSite: 'Lax' }])
    const stub = `
      const account = { username: ${JSON.stringify(USER)} };
      const instance = { initialize: async()=>{}, handleRedirectPromise: async()=>null,
        getAllAccounts: ()=>[account], acquireTokenSilent: async()=>({idToken:'stub',account}), loginRedirect: async()=>{} };
      export async function initMsal(){ return instance; }
      export class InteractionRequiredAuthError extends Error {}`
    await ctx.route('**/msal-init.js', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: stub }))
    await ctx.route('**/api/auth', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ identity: USER }) }))
    await ctx.route('**/api/analysis/**', async () => { await new Promise(res => setTimeout(res, 99999)) })
    const tab = await ctx.newPage()
    await tab.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' }).catch(() => {})
    await tab.waitForSelector('#library-view', { state: 'visible', timeout: 12000 }).catch(() => {})
    await tab.waitForTimeout(3500)
    const card = tab.locator('#grid > *').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click().catch(() => {})
      await tab.waitForTimeout(1500)
    }
    await tab.screenshot({ path: path.join(SHOT, `${TAG}.state-analysis-loading.desktop.png`), fullPage: true })
    console.log('✓ state-analysis-loading')
    await ctx.close()
  }

  await browser.close()
}
main().catch((e) => { console.error(e); process.exit(1) })
