// Browser-only fixture regression; does not validate a live API, worker or indexing.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
if(!process.argv[2])throw new Error('Provide a new output directory');
const output=path.resolve(process.argv[2]);fs.mkdirSync(path.dirname(output),{recursive:true});fs.mkdirSync(output);
const server=require('./browser_fixture.cjs').createServer();
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL || 'chrome'});
 const context=await browser.newContext({viewport:{width:1360,height:1040}});const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));const jobs=[];
 try{
  await page.goto(base+'/sales.html');await page.locator('#generate:not([disabled])').waitFor();
  assert.equal(await page.locator('nav a').count(),4);
  for(const [kind,expected] of [['monthly','3000.00'],['customer','1550.00'],['empty','0.00'],['clarification',null]]){
   if(kind!=='monthly')await page.locator('#new-task').click();
   await page.locator('#sales-case').selectOption(kind);
   let posts=0;const listener=req=>{if(req.method()==='POST'&&req.url().endsWith('/agent-runs'))posts++;};page.on('request',listener);
   const [creation]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/agent-runs')&&r.request().method()==='POST'),page.locator('#generate').click()]);
   const createdId=(await creation.json()).job.job_id;
   await page.waitForFunction(id=>document.getElementById('job-meta').textContent.includes(id),createdId);
   await page.waitForFunction(()=>new URL(location.href).searchParams.has('job'));
   await page.waitForFunction(()=>document.getElementById('job-title').textContent.includes('执行完成'),{},{timeout:90000});
   const id=new URL(page.url()).searchParams.get('job');jobs.push({kind,id});
   assert.equal(posts,1);assert(await page.locator('#generate').isDisabled());
   if(expected){assert((await page.locator('#metrics').innerText()).includes(expected));await page.locator('#review-approve:not([disabled])').waitFor();}
   else{assert((await page.locator('#job-status').innerText()).includes('需要补充'));assert(await page.locator('#approval-panel').isHidden());}
   await page.reload();await page.waitForFunction(()=>document.getElementById('job-title').textContent.includes('执行完成'));
   assert.equal(new URL(page.url()).searchParams.get('job'),id);assert.equal(posts,1);page.off('request',listener);
   if(kind==='monthly'){
    await page.locator('#review-approve:not([disabled])').click();await page.locator('#review-dialog[open]').waitFor();
    assert(await page.locator('#confirm-decision').isDisabled());assert((await page.locator('#review-meta').innerText()).includes('sales-manager-demo'));
    await page.locator('#review-check').check();await page.screenshot({path:path.join(output,'approval-review.png'),fullPage:true});
    await page.locator('#confirm-decision').click();await page.locator('#review-dialog[open]').waitFor({state:'hidden'});
    await page.waitForFunction(()=>document.getElementById('outbox').textContent.includes('已模拟发送 1 次'));
    assert.equal(await page.locator('#outbox .outbox-item').count(),1);await page.reload();await page.locator('#outbox .outbox-item').waitFor();
    await page.screenshot({path:path.join(output,'sales-desktop.png'),fullPage:true});
   }
   if(kind==='customer'){
    await page.locator('#review-reject:not([disabled])').click();await page.locator('#review-check').check();await page.locator('#confirm-decision').click();
    await page.waitForFunction(()=>document.getElementById('approval-status').textContent.includes('已拒绝'));
    assert.equal(await page.locator('#outbox .outbox-item').count(),0);
   }
  }
  await page.goto(base+'/sales.html?job='+jobs[0].id);await page.locator('#outbox .outbox-item').waitFor();
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'sales-mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  for(const [url,title]of [['/workflows.html','让模板成为可追踪的工作流'],['/evaluations.html','用同一把尺子评测 Agent']]){
   await page.goto(base+url);assert.equal(await page.locator('h1').innerText(),title);assert.equal(await page.locator('nav a').count(),4);}
  await page.goto(base+'/');await page.locator('#upload-form').waitFor();
  await page.locator('#file').setInputFiles(path.join(root,'demo/nebula-it-policy.md'));
  await page.locator('#upload-form button').click();
  await page.waitForFunction(()=>document.getElementById('upload-status').textContent.includes('已收录')||document.getElementById('upload-status').classList.contains('error'),{},{timeout:180000});
  assert((await page.locator('#upload-status').innerText()).includes('已收录'),await page.locator('#upload-status').innerText());
  await page.locator('#question').fill('P1 级故障需要多久响应？');await page.locator('#search-form button').click();
  await page.locator('#results article').first().waitFor({timeout:60000});
  assert((await page.locator('#results').innerText()).includes('nebula-it-policy.md'));
  assert.equal(await page.locator('#results img').count(),0);
  await page.screenshot({path:path.join(output,'knowledge-regression.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  const result={status:'passed',jobs,refresh_without_resubmission:true,one_simulated_message:true,rejection_no_send:true,mobile_no_overflow:true,scope:'browser_controls_with_fixed_local_responses',knowledge_upload_and_retrieval:'fixture_responses_only',real_worker_executed:false,page_errors:errors,external_send:false};
  fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
