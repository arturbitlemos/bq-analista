import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SHOT = path.join(__dirname, 'screenshots')
const file = 'file://' + path.join(__dirname, 'fixture-responsive.html')

async function launch() {
  try { return await chromium.launch({ headless: true }) }
  catch { return await chromium.launch({ headless: true, channel: 'chrome' }) }
}
const browser = await launch()
for (const [name, vp] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844, isMobile: true } })) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile })
  const tab = await ctx.newPage()
  await tab.goto(file, { waitUntil: 'networkidle' })
  const probe = await tab.evaluate(() => {
    const de = document.documentElement
    return {
      pageOverflow: de.scrollWidth - de.clientWidth,
      contentW: Math.round(document.querySelector('.page').getBoundingClientRect().width),
      viewportW: de.clientWidth,
      tableScrolls: (() => { const w = document.querySelector('.table-wrap'); return w.scrollWidth > w.clientWidth })(),
      minDataFont: Math.min(...[...document.querySelectorAll('td,.kpi .v')].map(e => parseFloat(getComputedStyle(e).fontSize))),
    }
  })
  await tab.screenshot({ path: path.join(SHOT, `fixture.${name}.png`), fullPage: true })
  console.log(name, JSON.stringify(probe))
  await ctx.close()
}
await browser.close()
