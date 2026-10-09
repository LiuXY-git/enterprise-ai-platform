// Capture the real frontend with explicitly synthetic, loopback HTTP responses.
// Requires Node >=20 and Playwright; never starts Docker or calls a business API.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const documentPath = 'demo/nebula-it-policy.md';
const documentBytes = fs.readFileSync(path.join(root, documentPath));
const documentText = documentBytes.toString('utf8').replace(/\r\n/g, '\n');
const section = documentText.split('### P1 级故障\n')[1].split('### P2 级故障')[0].trim();
const question = 'P1 级故障需要多久响应？没有响应时如何升级？';
const response = { results: [{ source: 'nebula-it-policy.md', chunk_index: 0, text: section }] };

async function main() {
  assert(process.argv.length === 3, 'Usage: node scripts/portfolio/capture_readme.cjs <new-output-directory>');
  const output = path.resolve(process.argv[2]);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.mkdirSync(output); // Fail rather than overwrite an existing capture.
  const calls = [];
  const server = http.createServer(async (req, res) => {
    try {
      const chunks = [];
      let size = 0;
      for await (const chunk of req) {
        size += chunk.length;
        if (size > 1024 * 1024) { res.writeHead(413); res.end(); return; }
        chunks.push(chunk);
      }
      const body = Buffer.concat(chunks).toString();
      if (req.url.startsWith('/api/')) {
        calls.push({ path: req.url, method: req.method });
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
        if (req.url === '/api/health' && req.method === 'GET') {
          res.end(JSON.stringify({ status: 'ok' })); return;
        }
        if (req.url === '/api/upload' && req.method === 'POST') {
          assert(body.includes('filename="nebula-it-policy.md"'));
          res.end(JSON.stringify({ status: 'indexed', filename: 'nebula-it-policy.md',
            document_id: 1, chunk_count: 1 })); return;
        }
        if (req.url === '/api/rag/query' && req.method === 'POST') {
          assert.deepEqual(JSON.parse(body), { question, top_k: 3 });
          res.end(JSON.stringify(response)); return;
        }
        res.writeHead(404); res.end('{}'); return;
      }
      const files = {
        '/': ['index.html', 'text/html; charset=utf-8'],
        '/app.js': ['app.js', 'application/javascript; charset=utf-8'],
        '/styles.css': ['styles.css', 'text/css; charset=utf-8'],
      };
      const item = files[req.url];
      if (!item) { res.writeHead(404); res.end(); return; }
      res.setHeader('Content-Type', item[1]);
      res.end(fs.readFileSync(path.join(root, 'frontend/public', item[0])));
    } catch {
      res.writeHead(400); res.end('Invalid fixture request');
    }
  });
  let browser;
  const errors = [];
  const checks = [];
  try {
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
    const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    const page = await browser.newPage({ viewport: { width: 1365, height: 1000 }, deviceScaleFactor: 1 });
    page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => new URL(route.request().url()).origin === origin
      ? route.continue() : route.abort());
    await page.goto(origin);
    await page.getByText('● 后端已连接').waitFor();
    checks.push('fixture health response displayed');
    await page.locator('#file').setInputFiles({
      name: 'nebula-it-policy.md', mimeType: 'text/markdown', buffer: documentBytes,
    });
    await page.getByRole('button', { name: '上传并建立索引' }).click();
    await page.getByText('已收录 nebula-it-policy.md，共 1 个片段（文档 #1）。').waitFor();
    checks.push('upload interaction and synthetic receipt displayed');
    await page.locator('#question').fill(question);
    await page.getByRole('button', { name: '检索知识库' }).click();
    await page.getByText('找到 1 个相关片段').waitFor();
    assert.equal(await page.locator('#results .result').count(), 1);
    assert.equal(await page.locator('#results .result p').textContent(), section);
    assert.equal(await page.locator('#results .result h3').textContent(), '1. nebula-it-policy.md');
    checks.push('source name and excerpt match the checked-in fictional document');
    await page.screenshot({ path: path.join(output, 'knowledge-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({ path: path.join(output, 'knowledge-mobile.png'), fullPage: true });
    checks.push('desktop and mobile captures; no horizontal overflow');
    assert.deepEqual(calls.map(c => c.path), ['/api/health', '/api/upload', '/api/rag/query']);
    assert.deepEqual(errors, []);
    checks.push('expected requests only; no browser script errors');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
  const sources = {};
  for (const name of ['frontend/public/index.html', 'frontend/public/app.js',
    'frontend/public/styles.css', documentPath, 'scripts/portfolio/capture_readme.cjs']) {
    sources[name] = crypto.createHash('sha256')
      .update(fs.readFileSync(path.join(root, name)).toString('utf8').replace(/\r\n/g, '\n')).digest('hex');
  }
  const screenshots = {};
  for (const name of ['knowledge-desktop.png', 'knowledge-mobile.png']) {
    screenshots[name] = crypto.createHash('sha256').update(fs.readFileSync(path.join(output, name))).digest('hex');
  }
  const report = { status: 'passed', mode: 'real_frontend_with_local_http_fixtures',
    captured_at: new Date().toISOString(), checks, sources, screenshots, question,
    browser_version: browser.version(), browser_errors: errors, fixture_calls: calls,
    real_ingestion_or_vector_search_tested: false, real_model_requests: 0,
    existing_frontend_started: false, temporary_server_stopped: true };
  fs.writeFileSync(path.join(output, 'capture.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: report.status, output_dir: output, checks: checks.length, mode: report.mode }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
