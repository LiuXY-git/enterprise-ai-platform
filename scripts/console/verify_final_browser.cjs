// Run after verify_extended_browser against the same disposable fixture stack.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const output=path.resolve(process.argv[2]||'');
if(!process.argv[2]||fs.existsSync(output))throw Error('Provide a new proof directory');
fs.mkdirSync(output,{recursive:true});
const base=process.env.CONSOLE_URL||'http://127.0.0.1:18080';
(async()=>{
 const b=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'chrome',headless:true});
 const context=await b.newContext({viewport:{width:1360,height:1000}}),p=await context.newPage();
 const errors=[];p.on('pageerror',e=>errors.push(e.message));
 const get=async route=>{const r=await context.request.get(base+'/api'+route);assert(r.ok());return r.json();};
 try{
  // Initial API failure and read-only recovery, with raw upstream HTML never displayed.
  let offline=true,posts=0;p.on('request',r=>{if(r.method()==='POST')posts++;});
  await p.route('**/api/console/capabilities',r=>offline?r.fulfill({status:502,contentType:'text/html',body:'<html>PRIVATE_UPSTREAM_TRACE</html>'}):r.continue());
  await p.goto(base+'/workflows.html');await p.waitForFunction(()=>document.querySelector('#console-error').textContent.includes('502'));
  assert(!(await p.locator('body').innerText()).includes('PRIVATE_UPSTREAM_TRACE'));
  offline=false;await p.locator('#retry-status').click();await p.locator('#submit-task:not([disabled])').waitFor();assert.equal(posts,0);
  await p.unroute('**/api/console/capabilities');
  const jobs=(await get('/jobs?kind=workflow&limit=100')).jobs.filter(j=>j.result&&j.mode==='fixture');
  const [a,c]=jobs;assert(a&&c);
  let count=0,release;const held=new Promise(resolve=>release=resolve);let signal;const requested=new Promise(resolve=>signal=resolve);
  await p.route('**/api/jobs/'+a.job_id,async route=>{count++;if(count===2){signal();await held;}await route.fulfill({json:a});});
  await p.goto(base+'/workflows.html?job='+a.job_id);await p.locator('#task-result h3').first().waitFor();await requested;
  await p.locator('#history-list button').filter({hasText:c.job_id.slice(0,8)}).click();release();
  await p.waitForTimeout(400);assert((await p.locator('#job-meta').innerText()).includes(c.job_id));
  await p.unroute('**/api/jobs/'+a.job_id);
  // Poll failure clears when connectivity returns and does not submit new work.
  let fail=true;await p.route('**/api/jobs/'+c.job_id,r=>fail?r.fulfill({status:503,json:{detail:'PRIVATE_UPSTREAM_TRACE'}}):r.continue());
  await p.waitForFunction(()=>document.querySelector('#console-error').textContent.includes('503'));fail=false;
  await p.waitForFunction(()=>document.querySelector('#console-error').textContent==='');await p.unroute('**/api/jobs/'+c.job_id);
  assert.equal(posts,0);
  const evaluation=(await get('/jobs?kind=evaluation&limit=100')).jobs.find(j=>j.status==='succeeded'&&j.result?.summary?.selected===12);assert(evaluation);
  const injected=structuredClone(evaluation);injected.result.summary.passed=11;injected.result.summary.errors=1;injected.result.summary.numerator=11;injected.result.summary.success_rate_percent=100*11/12;
  injected.result.cases[0].judgement='error';injected.result.cases[0].reason='evidence_invalid';
  await p.route('**/api/jobs/'+injected.job_id,r=>r.fulfill({json:injected}));
  await p.goto(base+'/evaluations.html?job='+injected.job_id);await p.locator('.report-link').waitFor();
  assert((await p.locator('#task-result').innerText()).includes('11 / 12'));await p.locator('#task-result details summary').first().click();assert((await p.locator('#task-result').innerText()).includes('evidence_invalid'));
  await p.screenshot({path:path.join(output,'injected-scoring-error.png'),fullPage:true});await p.unroute('**/api/jobs/'+injected.job_id);
  const sales=(await get('/jobs?kind=agent&limit=100')).jobs.find(j=>j.source_ids.approval_id);assert(sales);
  const approval=await get('/approvals/'+sales.source_ids.approval_id);const expired={...approval,effective_status:'expired',status:'pending',simulation_count:0,simulated_messages:[]};
  await p.route('**/api/approvals/'+approval.approval_id,r=>r.fulfill({json:expired}));
  await p.goto(base+'/sales.html?job='+sales.job_id);await p.waitForFunction(()=>document.querySelector('#approval-status').textContent.includes('已过期'));assert(await p.locator('#review-approve').isDisabled());
  await p.screenshot({path:path.join(output,'injected-expired-approval.png'),fullPage:true});await p.unroute('**/api/approvals/'+approval.approval_id);assert.equal(posts,0);
  // Real upload + local embedding + retrieval. No route interception here.
  await p.goto(base+'/');await p.locator('#file').setInputFiles(path.resolve(__dirname,'../../demo/nebula-it-policy.md'));await p.locator('#upload-form button').click();
  await p.waitForFunction(()=>document.querySelector('#upload-status').textContent.includes('已收录')||document.querySelector('#upload-status').classList.contains('error'),{},{timeout:180000});
  assert((await p.locator('#upload-status').innerText()).includes('已收录'),await p.locator('#upload-status').innerText());
  await p.locator('#question').fill('P1 级故障需要多久响应？');await p.locator('#search-form button').click();await p.locator('#results article').first().waitFor({timeout:120000});assert((await p.locator('#results').innerText()).includes('nebula-it-policy.md'));
  await p.screenshot({path:path.join(output,'knowledge-real.png'),fullPage:true});
  for(const url of ['/','/sales.html','/workflows.html','/evaluations.html']){await p.setViewportSize({width:390,height:844});await p.goto(base+url);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({status:'passed',real_checks:['knowledge_upload_index_retrieval','four_mobile_pages','navigation_no_post'],injected_ui_checks:['html_gateway_error_redacted','initial_failure_readonly_retry','stale_poll_cannot_replace_selected_job','transient_error_clears','scoring_error_keeps_denominator','expired_approval_disabled'],external_send:false},null,2));
  console.log('Final browser regression passed. Injected UI cases are separately labelled.');
 }finally{await context.close();await b.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
