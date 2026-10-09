// Export the fixed Day 100 SVG assets with a local, headless browser.
// Requires Node >=20 and Playwright. No HTTP server or business service is started.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const names = ['system-architecture', 'rag-data-flow'];
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

async function main() {
  assert(process.argv.length === 4,
    'Usage: node scripts/portfolio/export_architecture.cjs <svg-directory> <new-output-directory>');
  const source = path.resolve(process.argv[2]);
  const output = path.resolve(process.argv[3]);
  const inputs = names.map(name => {
    const filename = path.join(source, name + '.svg');
    const bytes = fs.readFileSync(filename);
    const xml = bytes.toString('utf8');
    assert(!/<script|<foreignObject|<!ENTITY|<!DOCTYPE|(?:href|src)\s*=|@import|url\(\s*['"]?(?!#)/i.test(xml),
      'Only standalone static SVG without external resources is allowed');
    return { name, filename, bytes };
  });
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.mkdirSync(output); // Keep previous exports intact.
  let browser;
  const report = { status: 'passed', mode: 'local_svg_render', assets: {}, network_requests: 0 };
  try {
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    report.browser = browser.version();
    report.node = process.version;
    const page = await browser.newPage({ deviceScaleFactor: 1 });
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => {
      if (inputs.some(input => pathToFileURL(input.filename).href === route.request().url())) {
        return route.continue();
      }
      report.network_requests++;
      return route.abort();
    });
    for (const input of inputs) {
      await page.goto(pathToFileURL(input.filename).href);
      await page.evaluate(() => document.fonts.ready);
      const dimensions = await page.evaluate(() => {
        const svg = document.documentElement;
        if (svg.tagName !== 'svg' || document.querySelector('parsererror')) throw Error('Invalid SVG');
        const bounds = svg.viewBox.baseVal;
        const violations = [];
        for (const text of document.querySelectorAll('text')) {
          const b = text.getBBox();
          if (b.x < 0 || b.y < 0 || b.x + b.width > bounds.width || b.y + b.height > bounds.height) {
            violations.push('canvas: ' + text.textContent);
          }
        }
        for (const card of document.querySelectorAll('[data-card]')) {
          const rect = card.querySelector('rect').getBBox();
          for (const text of card.querySelectorAll('text')) {
            const b = text.getBBox();
            if (b.x < rect.x + 10 || b.y < rect.y + 6 ||
                b.x + b.width > rect.x + rect.width - 10 || b.y + b.height > rect.y + rect.height - 4) {
              violations.push(card.getAttribute('data-card') + ': ' + text.textContent);
            }
          }
        }
        return { width: bounds.width, height: bounds.height, violations,
          cards: document.querySelectorAll('[data-card]').length,
          text_elements: document.querySelectorAll('text').length };
      });
      assert.deepEqual(dimensions.violations, [], 'Diagram text must fit inside its card and canvas');
      await page.setViewportSize({ width: dimensions.width, height: dimensions.height });
      const png = await page.locator('svg').screenshot({ path: path.join(output, input.name + '.png') });
      report.assets[input.name] = { ...dimensions, svg_sha256: digest(input.bytes), png_sha256: digest(png) };
    }
    assert.deepEqual(errors, []);
    assert.equal(report.network_requests, 0);
    report.browser_errors = errors;
  } finally {
    if (browser) await browser.close();
  }
  report.browser_closed = true;
  fs.writeFileSync(path.join(output, 'render.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
