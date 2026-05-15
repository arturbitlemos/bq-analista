// Audits the analysis HTML itself (the iframe content) — where the product's
// real value lives. Loads /api/analysis/<id> directly with a session cookie.
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mintSessionCookie } from './cookie.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHOT = path.join(__dirname, 'screenshots')
const FIND = path.join(__dirname, 'findings')
const BASE = process.env.BASE_URL || 'http://localhost:3001'
const USER = 'artur.lemos@somagrupo.com.br'
const TAG = process.env.AUDIT_TAG || 'dash-pre'

const IDS = [
  { id: 'farm-taxa-de-devolu-o-por-produto-inv26-ai26-ytd-2026-6316465e', slug: 'farm-devolucao' },
  { id: 'azzas-2154-venda-ytd-por-marca-e-canal-2026-vs-2025-6a3a27de', slug: 'azzas-venda-ytd' },
  { id: 'maria-fil-vendas-por-tamanho-regi-o-grupo-mtd-abr-26-9192012f', slug: 'mariafilo-tamanho' },
]
const VPS = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844, isMobile: true } }

async function launch() {
  try { return await chromium.launch({ headless: true }) }
  catch { return await chromium.launch({ headless: true, channel: 'chrome' }) }
}

async function main() {
  fs.mkdirSync(SHOT, { recursive: true }); fs.mkdirSync(FIND, { recursive: true })
  const browser = await launch()
  const out = { ts: new Date().toISOString(), tag: TAG, reports: [] }

  for (const a of IDS) {
    for (const [vpName, vp] of Object.entries(VPS)) {
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        isMobile: !!vp.isMobile, hasTouch: !!vp.isMobile,
        userAgent: vp.isMobile ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' : undefined,
      })
      await ctx.addCookies([{ name: 'session', value: mintSessionCookie(USER), domain: new URL(BASE).hostname, path: '/', sameSite: 'Lax' }])
      const tab = await ctx.newPage()
      const store = { console: [], errors: [] }
      tab.on('console', m => { if (m.type() === 'error') store.console.push(m.text().slice(0, 140)) })
      tab.on('pageerror', e => store.errors.push(e.message.slice(0, 140)))

      const t0 = Date.now()
      await tab.goto(`${BASE}/api/analysis/${encodeURIComponent(a.id)}`, { waitUntil: 'domcontentloaded', timeout: 25000 }).catch(() => {})
      await tab.waitForTimeout(3500) // let charts render
      const ms = Date.now() - t0

      const probe = await tab.evaluate(() => {
        const de = document.documentElement
        const horizOverflow = de.scrollWidth - de.clientWidth
        const bodyText = document.body?.innerText || ''
        const tierLabels = (bodyText.match(/[✅📊🔶❓]/g) || []).length
        const tables = [...document.querySelectorAll('table')].map(t => ({
          w: Math.round(t.getBoundingClientRect().width),
          overflowsViewport: t.getBoundingClientRect().width > de.clientWidth + 2,
        }))
        const tinyText = [...document.querySelectorAll('body *')].filter(el => {
          const s = parseFloat(getComputedStyle(el).fontSize)
          return el.children.length === 0 && el.textContent.trim() && s > 0 && s < 11
        }).length
        const charts = document.querySelectorAll('canvas, svg.plotly, .js-plotly-plot, [class*="chart"]').length
        const viewportMeta = !!document.querySelector('meta[name="viewport"]')
        const hasHomeBg = getComputedStyle(document.body).backgroundColor
        return {
          horizOverflow, tierLabels, tables, tinyTextNodes: tinyText, charts, viewportMeta,
          scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, bodyBg: hasHomeBg,
          docTitle: document.title, h1: document.querySelector('h1,h2')?.innerText?.slice(0, 80) || null,
        }
      }).catch(e => ({ error: e.message }))

      const shot = path.join(SHOT, `${TAG}.${a.slug}.${vpName}.png`)
      await tab.screenshot({ path: shot, fullPage: true }).catch(() => {})
      out.reports.push({ id: a.id, slug: a.slug, vp: vpName, ms, probe, console: store.console.slice(0, 8), errors: store.errors.slice(0, 8), shot: path.relative(__dirname, shot) })
      console.log(`✓ ${a.slug} ${vpName}  overflow=${probe.horizOverflow}px tiers=${probe.tierLabels} charts=${probe.charts} tinyText=${probe.tinyTextNodes}`)
      await ctx.close()
    }
  }
  await browser.close()
  fs.writeFileSync(path.join(FIND, `${TAG}.json`), JSON.stringify(out, null, 2))
  console.log(`\nFindings: ${path.join(FIND, `${TAG}.json`)}`)
}
main().catch(e => { console.error(e); process.exit(1) })
