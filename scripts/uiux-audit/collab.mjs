// Exercises collaboration flows: card kebab → share modal, refresh modal,
// at desktop + mobile. Drives the real library via the MSAL stub.
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mintSessionCookie } from './cookie.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHOT = path.join(__dirname, 'screenshots')
const FIND = path.join(__dirname, 'findings')
const BASE = 'http://localhost:3001'
const USER = 'artur.lemos@somagrupo.com.br'
const TAG = process.env.AUDIT_TAG || 'collab-pre'

const MSAL = `
const account = { username: ${JSON.stringify(USER)} };
const instance = { initialize: async()=>{}, handleRedirectPromise: async()=>null,
  getAllAccounts: ()=>[account], acquireTokenSilent: async()=>({idToken:'stub',account}), loginRedirect: async()=>{} };
export async function initMsal(){ return instance; }
export class InteractionRequiredAuthError extends Error {}`

async function launch() {
  try { return await chromium.launch({ headless: true }) }
  catch { return await chromium.launch({ headless: true, channel: 'chrome' }) }
}

async function ctxFor(browser, vp) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.m, hasTouch: !!vp.m })
  await ctx.addCookies([{ name: 'session', value: mintSessionCookie(USER), domain: 'localhost', path: '/', sameSite: 'Lax' }])
  await ctx.route('**/msal-init.js', r => r.fulfill({ status: 200, contentType: 'application/javascript', body: MSAL }))
  await ctx.route('**/api/auth', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ identity: USER }) }))
  // never actually mutate ACLs/refresh on the real server during the audit
  await ctx.route('**/api/share', r => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }))
  await ctx.route('**/api/refresh-proxy', r => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }))
  return ctx
}

async function openLibrary(ctx) {
  const tab = await ctx.newPage()
  const errs = []
  tab.on('pageerror', e => errs.push(e.message.slice(0, 140)))
  await tab.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' }).catch(() => {})
  await tab.waitForSelector('#library-view', { state: 'visible', timeout: 12000 }).catch(() => {})
  await tab.waitForTimeout(3500)
  return { tab, errs }
}

async function main() {
  fs.mkdirSync(SHOT, { recursive: true }); fs.mkdirSync(FIND, { recursive: true })
  const browser = await launch()
  const out = { ts: new Date().toISOString(), tag: TAG, steps: [] }

  for (const [vpName, vp] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844, m: true } })) {
    const ctx = await ctxFor(browser, vp)
    const { tab, errs } = await openLibrary(ctx)

    // open kebab on first card
    const kebab = tab.locator('#grid .card-menu').first()
    let menuItems = []
    if (await kebab.isVisible().catch(() => false)) {
      await kebab.click().catch(() => {})
      await tab.waitForTimeout(500)
      menuItems = await tab.locator('.card-menu-dropdown.open button').allInnerTexts().catch(() => [])
      await tab.screenshot({ path: path.join(SHOT, `${TAG}.kebab.${vpName}.png`), fullPage: true })
    }
    out.steps.push({ vp: vpName, step: 'kebab', menuItems })

    // share modal
    const shareBtn = tab.locator('.card-menu-dropdown.open button[data-action="share-people"]')
    if (await shareBtn.count().catch(() => 0)) {
      await shareBtn.first().click().catch(() => {})
      await tab.waitForTimeout(700)
      await tab.locator('#share-emails-input').fill('colega@somagrupo.com.br').catch(() => {})
      await tab.locator('#share-emails-input').press('Enter').catch(() => {})
      await tab.waitForTimeout(400)
      await tab.screenshot({ path: path.join(SHOT, `${TAG}.share-modal.${vpName}.png`), fullPage: true })
      const chips = await tab.locator('#share-chips-wrap .chip').count().catch(() => 0)
      out.steps.push({ vp: vpName, step: 'share-modal', chips })
      await tab.keyboard.press('Escape').catch(() => {})
      await tab.waitForTimeout(300)
    } else {
      out.steps.push({ vp: vpName, step: 'share-modal', note: 'share-people not in menu (item public/not mine?)' })
    }

    // re-open kebab → refresh modal
    await kebab.click().catch(() => {})
    await tab.waitForTimeout(400)
    const refreshBtn = tab.locator('.card-menu-dropdown.open button[data-action="refresh"]')
    if (await refreshBtn.count().catch(() => 0)) {
      await refreshBtn.first().click().catch(() => {})
      await tab.waitForTimeout(700)
      await tab.screenshot({ path: path.join(SHOT, `${TAG}.refresh-modal.${vpName}.png`), fullPage: true })
      out.steps.push({ vp: vpName, step: 'refresh-modal', ok: true })
      await tab.keyboard.press('Escape').catch(() => {})
    } else {
      out.steps.push({ vp: vpName, step: 'refresh-modal', note: 'refresh not in menu (no refresh_spec)' })
    }

    out.steps.push({ vp: vpName, step: 'pageerrors', errs })
    await ctx.close()
  }
  await browser.close()
  fs.writeFileSync(path.join(FIND, `${TAG}.json`), JSON.stringify(out, null, 2))
  console.log(JSON.stringify(out.steps, null, 1))
}
main().catch(e => { console.error(e); process.exit(1) })
