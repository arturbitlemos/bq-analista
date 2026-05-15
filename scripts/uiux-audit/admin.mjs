// Audits the ADMIN analytics dashboard AS AN ADMIN by stubbing the two admin
// APIs with synthetic aggregate fixtures. Real admin data contains individual
// emails (PII) — never pulled into context; fixtures are fake aggregates.
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mintSessionCookie } from './cookie.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHOT = path.join(__dirname, 'screenshots')
const FIND = path.join(__dirname, 'findings')
const BASE = 'http://localhost:3001'
const USER = 'admin.fixture@somagrupo.com.br'
const TAG = process.env.AUDIT_TAG || 'admin-post'

const today = new Date()
const dayStr = (d) => new Date(today - d * 864e5).toISOString().slice(0, 10)

const ANALYTICS = {
  summary: { total_publishes: 312, total_refreshes: 1487, total_shares: 96, total_archives: 41, distinct_users: 58, total_login_failures: 3 },
  by_action_by_day: Array.from({ length: 14 }).flatMap((_, i) => ([
    { day: dayStr(i), action: 'publish', n: 10 + (i % 5) },
    { day: dayStr(i), action: 'refresh', n: 40 + (i % 9) * 3 },
    { day: dayStr(i), action: 'share', n: 2 + (i % 3) },
    { day: dayStr(i), action: 'archive', n: i % 2 },
  ])),
  top_users: Array.from({ length: 12 }).map((_, i) => ({ actor_email: `user${i + 1}.fixture@somagrupo.com.br`, n: 240 - i * 17 })),
  top_analyses: Array.from({ length: 10 }).map((_, i) => ({ title: `Análise fixture muito longa pra testar truncamento de título número ${i + 1}`, analysis_id: `an_${1000 + i}`, n: 88 - i * 6 })),
  recent_activity: Array.from({ length: 20 }).map((_, i) => ({ occurred_at: new Date(today - i * 36e5).toISOString(), actor_email: `user${(i % 12) + 1}.fixture@somagrupo.com.br`, action: ['publish', 'refresh', 'share', 'archive'][i % 4], analysis_id: `an_${1000 + (i % 10)}` })),
}

const BQ = {
  totals: { total_calls: 9123, total_errors: 47, total_bytes_scanned: 4.7e12, distinct_users: 58 },
  by_day: Array.from({ length: 30 }).flatMap((_, i) => ([
    { day: dayStr(i), exec_email: 'user1.fixture@somagrupo.com.br', n: 30 + (i % 7) },
    { day: dayStr(i), exec_email: 'user2.fixture@somagrupo.com.br', n: 12 + (i % 4) },
  ])),
  by_user: Array.from({ length: 14 }).map((_, i) => ({ exec_email: `user${i + 1}.fixture@somagrupo.com.br`, total_calls: 900 - i * 55, errors: i % 3, total_bytes: 3.2e11 - i * 1e10, avg_duration_ms: 1200 + i * 90, top_agent: ['vendas-linx', 'devolucoes', 'ciclo-de-venda-atacado'][i % 3] })),
  recent_errors: Array.from({ length: 6 }).map((_, i) => ({ ts: Math.floor((today - i * 72e5) / 1000), exec_email: `user${i + 1}.fixture@somagrupo.com.br`, agent: 'vendas-linx', sql_preview: 'SELECT rede_lojas, SUM(venda_liquida) FROM `proj.ds.fato_vendas` WHERE data_venda >= ...', error: 'Query exceeded resource limits / timeout after 60000ms' })),
  last_seen_by_agent: [
    { agent: 'vendas-linx', last_seen: new Date(today - 12 * 6e4).toISOString() },
    { agent: 'devolucoes', last_seen: new Date(today - 5 * 36e5).toISOString() },
    { agent: 'ciclo-de-venda-atacado', last_seen: new Date(today - 3 * 864e5).toISOString() },
  ],
}

async function launch() {
  try { return await chromium.launch({ headless: true }) }
  catch { return await chromium.launch({ headless: true, channel: 'chrome' }) }
}

async function main() {
  fs.mkdirSync(SHOT, { recursive: true }); fs.mkdirSync(FIND, { recursive: true })
  const browser = await launch()
  const out = { ts: new Date().toISOString(), tag: TAG, views: [] }

  for (const [vpName, vp] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844, m: true } })) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.m, hasTouch: !!vp.m })
    await ctx.addCookies([{ name: 'session', value: mintSessionCookie(USER), domain: 'localhost', path: '/', sameSite: 'Lax' }])
    await ctx.route('**/api/admin/analytics', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ANALYTICS) }))
    await ctx.route('**/api/admin/bq-stats**', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BQ) }))
    const tab = await ctx.newPage()
    const errs = []
    tab.on('pageerror', e => errs.push(e.message.slice(0, 160)))
    await tab.goto(`${BASE}/admin`, { waitUntil: 'domcontentloaded' }).catch(() => {})
    await tab.waitForSelector('.cards .value', { timeout: 12000 }).catch(() => {})
    await tab.waitForTimeout(2500)

    const denied = await tab.locator('.denied').isVisible().catch(() => false)
    const cards = await tab.locator('.cards .card').count().catch(() => 0)
    const tables = await tab.locator('table').count().catch(() => 0)
    const chart = await tab.locator('#bq-chart').isVisible().catch(() => false)
    // horizontal overflow check (mobile pain on wide tables)
    const overflow = await tab.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth).catch(() => -1)
    await tab.screenshot({ path: path.join(SHOT, `${TAG}.admin.${vpName}.png`), fullPage: true })

    // exercise the 7d/30d/90d switch
    let switched = false
    const btn7 = tab.locator('.time-btn[data-days="7"]')
    if (await btn7.count().catch(() => 0)) {
      await btn7.first().click().catch(() => {})
      await tab.waitForTimeout(800)
      switched = await tab.locator('.time-btn[data-days="7"].active').isVisible().catch(() => false)
    }

    out.views.push({ vp: vpName, denied, cards, tables, chart, hOverflowPx: overflow, timeSwitchWorks: switched, pageerrors: errs })
    await ctx.close()
  }
  await browser.close()
  fs.writeFileSync(path.join(FIND, `${TAG}.json`), JSON.stringify(out, null, 2))
  console.log(JSON.stringify(out.views, null, 1))
}
main().catch(e => { console.error(e); process.exit(1) })
