// Explicit opt-in: submits one real request per template, never retries a task.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const output = process.argv[2] && path.resolve(process.argv[2]);
if (!output || process.argv[3] !== '--confirm-live' || fs.existsSync(output)) {
  throw Error('Provide a new output directory followed by --confirm-live');
}
fs.mkdirSync(output, { recursive: true });
const base = process.env.CONSOLE_URL || 'http://127.0.0.1:18080';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'chrome' });
  const context = await browser.newContext({ viewport: { width: 1360, height: 1040 } });
  const page = await context.newPage();
  const proof = { status: 'failed', scope: 'real_browser_api_worker_n8n', jobs: [], external_send: false };
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto(base + '/workflows.html');
    await page.locator('#submit-task:not([disabled])').waitFor();
    const capabilities = await (await context.request.get(base + '/api/console/capabilities')).json();
    assert(capabilities.workflow_templates.every(t => t.live_configured), 'Configure n8n before running this opt-in check');
    for (const template of ['customer-service', 'email-assistant', 'sales-followup']) {
      await page.locator('#new-task').click();
      await page.locator('#template').selectOption(template);
      if (template === 'customer-service') await page.locator('#field-message').fill('演示咨询：知识库支持哪些文档格式？');
      if (template === 'email-assistant') {
        await page.locator('#field-subject').fill('演示：文档格式咨询');
        await page.locator('#field-body').fill('请说明知识库支持哪些文档格式，仅生成回复草稿。');
      }
      await page.locator('#workflow-mode').selectOption('live');
      await page.locator('#live-confirm').check();
      const response = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/workflow-executions'));
      await page.locator('#submit-task').click();
      const submitted = await (await response).json();
      const id = submitted.job.job_id;
      proof.jobs.push({ template_id: template, job_id: id });
      fs.writeFileSync(path.join(output, 'verification.json'), JSON.stringify(proof, null, 2));
      const deadline = Date.now() + 180000;
      let job;
      do {
        job = await (await context.request.get(base + '/api/jobs/' + id)).json();
        if (!['queued', 'running'].includes(job.status)) break;
        await page.waitForTimeout(500);
      } while (Date.now() < deadline);
      Object.assign(proof.jobs.at(-1), { status: job.status, result: job.result, error: job.error });
      assert.equal(job.status, 'succeeded', JSON.stringify(job.error));
      assert(['succeeded', 'completed'].includes(job.result?.business_status), 'Check the recorded event in n8n; do not automatically retry');
      assert.equal(job.result.external_send, false);
      assert.equal(job.result.automatic_replay, false);
      assert(job.result.source_ids.n8n_execution_id);
      await page.waitForFunction(() => document.querySelector('#task-result').textContent.includes('n8n 回执'));
      await page.screenshot({ path: path.join(output, template + '.png'), fullPage: true });
      let posts = 0;
      const listener = r => { if (r.method() === 'POST') posts++; };
      page.on('request', listener);
      await page.reload();
      await page.waitForFunction(() => document.querySelector('#task-result').textContent.includes('n8n 回执'));
      assert.equal(posts, 0);
      page.off('request', listener);
    }
    assert.deepEqual(errors, []);
    proof.status = 'passed';
    console.log(JSON.stringify({ status: proof.status, jobs: proof.jobs.map(j => ({ template: j.template_id, id: j.job_id, sources: j.result.source_ids })) }));
  } finally {
    fs.writeFileSync(path.join(output, 'verification.json'), JSON.stringify(proof, null, 2));
    await context.close();
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
