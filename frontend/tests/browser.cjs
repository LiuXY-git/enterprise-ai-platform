// Local HTTP fixtures: browser behavior only, not Nginx or model validation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const output = path.resolve(process.env.BROWSER_OUTPUT || 'logs/day93-browser');
  fs.mkdirSync(output, { recursive: true });
  let mode = 'success';
  const calls = [];
  const server = http.createServer(async (req, res) => {
    if (req.url.startsWith('/api/')) {
      const parts = [];
      for await (const part of req) parts.push(part);
      calls.push({ path: req.url, body: Buffer.concat(parts).toString() });
      res.setHeader('Content-Type', 'application/json');
      if (mode === 'error') { res.writeHead(503); res.end('{}'); return; }
      if (req.url === '/api/health') { res.end('{"status":"ok"}'); return; }
      if (req.url === '/api/upload') {
        res.end(JSON.stringify({ status: 'indexed', filename: 'fixture.md', document_id: 27, chunk_count: 1 }));
        return;
      }
      if (req.url === '/api/rag/query') {
        await new Promise(resolve => setTimeout(resolve, 100));
        res.end(JSON.stringify({ results: mode === 'empty' ? [] : [{
          source: '<img src=x onerror="window.injected=1">', chunk_index: 0,
          text: '<script>window.injected=1</script>\n固定检索片段',
        }] }));
        return;
      }
      res.writeHead(404); res.end('{}'); return;
    }
    const files = { '/': ['index.html', 'text/html'], '/app.js': ['app.js', 'application/javascript'], '/styles.css': ['styles.css', 'text/css'] };
    const item = files[req.url];
    if (!item) { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', item[1] + '; charset=utf-8');
    res.end(fs.readFileSync(path.join(__dirname, '..', 'public', item[0])));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  const checks = [];
  try {
    browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || undefined });
    const page = await browser.newPage({ viewport: { width: 1365, height: 1000 } });
    page.setDefaultTimeout(10000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const origin = 'http://127.0.0.1:' + server.address().port;
    await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await page.goto(origin);
    await page.getByText('● 后端已连接').waitFor();
    checks.push('health through same-origin API path');
    await page.locator('#file').setInputFiles({ name: 'fixture.md', mimeType: 'text/markdown', buffer: Buffer.from('# Fixture') });
    await page.getByRole('button', { name: '上传并建立索引' }).click();
    await page.getByText('已收录 fixture.md，共 1 个片段（文档 #27）。').waitFor();
    assert(calls.find(c => c.path === '/api/upload').body.includes('name="file"; filename="fixture.md"'));
    checks.push('multipart upload and indexed receipt');
    const uploads = calls.filter(c => c.path === '/api/upload').length;
    await page.locator('#file').setInputFiles({ name: 'bad.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('x') });
    await page.getByRole('button', { name: '上传并建立索引' }).click();
    await page.getByText('请选择非空的 PDF、DOCX 或 MD 文件，且小于 10 MB。').waitFor();
    assert.equal(calls.filter(c => c.path === '/api/upload').length, uploads);
    checks.push('invalid upload rejected before request');
    await page.locator('#question').fill('   ');
    await page.getByRole('button', { name: '检索知识库' }).click();
    await page.getByText('请输入要查找的问题。').waitFor();
    assert(!calls.some(c => c.path === '/api/rag/query'));
    checks.push('blank search rejected before request');
    await page.locator('#question').fill('  流程  ');
    await page.getByRole('button', { name: '检索知识库' }).click();
    await page.locator('#search-form').evaluate(form => form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true })));
    await page.getByText('找到 1 个相关片段').waitFor();
    const searches = calls.filter(c => c.path === '/api/rag/query');
    assert.equal(searches.length, 1);
    assert.deepEqual(JSON.parse(searches[0].body), { question: '流程', top_k: 3 });
    assert.equal(await page.locator('#results img, #results script').count(), 0);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    checks.push('query payload, duplicate submit guard, untrusted text rendering');
    mode = 'empty';
    await page.getByRole('button', { name: '检索知识库' }).click();
    await page.getByText('未找到片段，请先上传文档。').waitFor();
    assert.equal(await page.locator('#results article').count(), 0);
    checks.push('empty results clear stale content');
    mode = 'error';
    await page.getByRole('button', { name: '检索知识库' }).click();
    await page.locator('#search-status.error').waitFor();
    assert((await page.locator('#search-status').textContent()).includes('HTTP 503'));
    assert(await page.getByRole('button', { name: '检索知识库' }).isEnabled());
    checks.push('HTTP failure and form recovery');
    await page.getByRole('button', { name: '重新检查' }).click();
    await page.locator('#health.error').waitFor();
    mode = 'success';
    await page.getByRole('button', { name: '重新检查' }).click();
    await page.getByText('● 后端已连接').waitFor();
    checks.push('health failure and recovery');
    await page.reload();
    await page.getByText('● 后端已连接').waitFor();
    await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    checks.push('desktop and mobile layout');
    assert.deepEqual(errors, []);
    const report = { status: 'passed', mode: 'local_http_fixtures', checks, browser_errors: errors, docker_tested: false };
    fs.writeFileSync(path.join(output, 'browser.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
