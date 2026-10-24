// Browser checks against the real isolated API/worker. Explicit local simulation only.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const output=path.resolve(process.argv[2]||'');if(!process.argv[2]||fs.existsSync(output))throw Error('Provide a new output directory');fs.mkdirSync(output,{recursive:true});
const base=process.env.CONSOLE_URL||'http://127.0.0.1:18080';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'chrome'});
 const context=await browser.newContext({viewport:{width:1360,height:1040}});const page=await context.newPage();
 const errors=[],jobs=[];page.on('pageerror',e=>errors.push(e.message));
 const json=async url=>(await context.request.get(base+'/api'+url)).json();
 try{
  await page.goto(base+'/workflows.html');await page.locator('#submit-task:not([disabled])').waitFor();
  for(const template of ['customer-service','email-assistant','sales-followup']){
   await page.locator('#new-task').click();await page.locator('#template').selectOption(template);
   if(template==='customer-service')await page.locator('#field-message').fill('<img src=x onerror=alert(1)> 页面演示');
   const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/workflow-executions'));
   await page.locator('#submit-task').click();const job=(await (await response).json()).job;jobs.push(job.job_id);
   await page.waitForFunction(()=>document.querySelector('#task-result').textContent.includes('演示完成'),{},{timeout:180000});
   assert.equal(await page.locator('#task-result img').count(),0);
   let posts=0;const listener=r=>{if(r.method()==='POST')posts++;};page.on('request',listener);await page.reload();await page.waitForFunction(()=>document.querySelector('#task-result').textContent.includes('演示完成'));assert.equal(posts,0);page.off('request',listener);
  }
  await page.screenshot({path:path.join(output,'workflows-desktop.png'),fullPage:true});
  await page.locator('#new-task').click();await page.locator('#workflow-mode').selectOption('live');await page.locator('#live-confirm').check();
  await page.locator('#submit-task').click();await page.waitForFunction(()=>document.querySelector('#job-status').textContent.includes('未配置'),{},{timeout:180000});
  await page.goto(base+'/evaluations.html');await page.locator('#submit-task:not([disabled])').waitFor();
  assert.equal(await page.locator('#suite').inputValue(),'full');
  const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/evaluation-runs'));
  await page.locator('#submit-task').click();const job=(await (await response).json()).job;jobs.push(job.job_id);
  await page.waitForFunction(()=>document.querySelector('#progress-caption').textContent.includes('例已执行'),{},{timeout:180000});
  await page.waitForFunction(()=>document.querySelector('#task-result .report-link')||document.querySelector('#job-title').textContent.includes('执行失败'),{},{timeout:950000});
  const result=(await json('/jobs/'+job.job_id)).result;
  assert.equal(result.summary.denominator,12);assert.equal(result.summary.passed,12);
  assert((await page.locator('#task-result').textContent()).includes('12 / 12'));
  const download=await context.request.get(base+'/api/jobs/'+job.job_id+'/report');assert.deepEqual(await download.json(),result);
  const details=page.locator('#task-result details').first();await details.locator('summary').click();await page.waitForTimeout(2000);assert.equal(await details.getAttribute('open'),'');
  await page.screenshot({path:path.join(output,'evaluations-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'evaluations-mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:1360,height:1040});
  // Supplement the previously blocked sales/HITL browser acceptance using real fixture runs.
  await page.goto(base+'/sales.html');await page.locator('#generate:not([disabled])').waitFor();
  await page.locator('#generate').click();await page.locator('#review-approve:not([disabled])').waitFor({timeout:90000});
  await page.locator('#review-approve').click();await page.locator('#review-check').check();await page.locator('#confirm-decision').click();
  await page.waitForFunction(()=>document.querySelector('#approval-status').textContent.includes('已模拟发送'),{},{timeout:180000});
  const salesId=new URL(page.url()).searchParams.get('job');jobs.push(salesId);const sales=await json('/jobs/'+salesId);
  const approval=await json('/approvals/'+sales.source_ids.approval_id);assert.equal(approval.simulation_count,1);assert.equal(approval.external_send,false);
  await page.reload();await page.waitForFunction(()=>document.querySelector('#approval-status').textContent.includes('已模拟发送'));
  assert.equal((await json('/approvals/'+sales.source_ids.approval_id)).simulation_count,1);
  await page.screenshot({path:path.join(output,'sales-approved.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({status:'passed',scope:'real_browser_api_linux_worker_fixture_models',jobs,checks:['three_workflow_forms','fixture_safe_text','refresh_no_post','missing_live_configuration','full_evaluation','download_matches_current_job','details_survive_poll','mobile_no_overflow','sales_generation_and_approval','approval_refresh_no_second_send'],external_send:false,live_dependencies_verified:false},null,2));
  console.log(JSON.stringify({status:'passed',output,jobs}));
 }finally{await context.close();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
