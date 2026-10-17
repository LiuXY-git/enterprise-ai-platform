import {$,text,request,post,labels,date} from './console-api.js';

let cases=[], selected=null, current=null, proposal=null, review=null, offset=0, busy=false, polling=false, pollError='';
const storageKey='eap.console.sales.submission.v1';
let pending=null;
try { pending=JSON.parse(localStorage.getItem(storageKey)); } catch { /* optional local cache */ }
if(!pending || !['monthly','customer','empty','clarification'].includes(pending.case) || !/^[a-zA-Z0-9-]+$/.test(pending.key || '')) pending=null;
const save=()=>{try {if(pending)localStorage.setItem(storageKey,JSON.stringify(pending));else localStorage.removeItem(storageKey);}catch{/* URL and server history still work */}};
const caseName=(id)=>cases.find(c=>c.id===id)?.label || id;
function controls() {
  $('generate').disabled=busy || cases.length===0 || Boolean(pending?.job_id);
  $('sales-case').disabled=busy || cases.length===0 || Boolean(pending);
  $('new-task').disabled=busy || !pending;
  $('generate').textContent=pending&&!pending.job_id?'重试同一提交':'生成简报';
}
function selectJob(id) {
  selected=id; current=null; proposal=null;
  const url=new URL(location.href); url.searchParams.set('job',id);history.replaceState(null,'',url);
  $('sales-result').hidden=true;$('approval-panel').hidden=true;text('job-status','正在读取任务…');
  text('decision-state',''); void loadJob().catch(showError);
}
function showError(e) {text('console-error',e.message);}
function scope() {text('case-scope',cases.find(c=>c.id===$('sales-case').value)?.scope || '');}
$('sales-case').addEventListener('change',scope);
$('new-task').addEventListener('click',()=>{pending=null;save();controls();text('submit-state','请确认场景后生成一份新任务。');});
$('agent-form').addEventListener('submit',async event=>{
  event.preventDefault();if($('generate').disabled||busy)return;
  busy=true;text('console-error','');
  pending ||= {key:crypto.randomUUID(),case:$('sales-case').value};save();controls();
  text('submit-state','正在提交…');
  try {
    const data=await post('/agent-runs',{case:pending.case,mode:'fixture'},pending.key);
    pending.job_id=data.job.job_id;save();selectJob(data.job.job_id);
    text('submit-state',data.reused?'已找回同一任务，没有重复创建。':'已入队；生成不会批准或发送。');await loadHistory();
  } catch(e){showError(e);text('submit-state','保留了提交编号，可重试同一提交。');}
  finally{busy=false;controls();}
});
async function loadHistory() {
  text('history-state','正在读取…');
  const data=await request(`/jobs?kind=agent&limit=8&offset=${offset}`);
  $('history-list').replaceChildren();
  for(const job of data.jobs) {
    const button=document.createElement('button');button.type='button';button.className='history-item'+(job.job_id===selected?' active':'');
    const title=document.createElement('span');title.textContent=`${caseName(job.input.case)} · ${labels[job.status]}`;
    const meta=document.createElement('small');meta.textContent=`${date(job.created_at)} · ${job.job_id.slice(0,8)}`;
    button.append(title,meta);button.addEventListener('click',()=>selectJob(job.job_id));$('history-list').append(button);
  }
  text('history-state',data.total?`共 ${data.total} 条 · 第 ${Math.floor(offset/8)+1} 页`:'暂无任务，生成第一份简报。');
  $('previous').disabled=offset===0;$('next').disabled=offset+8>=data.total;
}
$('history-refresh').addEventListener('click',()=>loadHistory().catch(showError));
$('previous').addEventListener('click',()=>{offset=Math.max(0,offset-8);void loadHistory().catch(showError);});
$('next').addEventListener('click',()=>{offset+=8;void loadHistory().catch(showError);});
function metric(label,value) {
  const div=document.createElement('div');div.className='metric';const strong=document.createElement('strong');strong.textContent=value;const span=document.createElement('span');span.textContent=label;div.append(strong,span);$('metrics').append(div);
}
async function loadJob() {
  const id=selected;if(!id)return;
  const job=await request(`/jobs/${encodeURIComponent(id)}`);if(selected!==id)return;
  if(job.kind!=='agent')throw new Error('此编号不是销售任务。');current=job;
  text('job-title',`${caseName(job.input.case)} · ${labels[job.status]}`);
  text('job-meta',`任务 ${job.job_id}\n创建 ${date(job.created_at)} · 完成 ${date(job.finished_at)}`);
  text('job-status',job.error?`${labels[job.status]}（${job.error.code}）。请核对记录；系统不会自动重跑。`:job.status==='queued'?'等待执行器领取；刷新不会创建新任务。':job.status==='running'?'正在执行 MCP 查询与简报校验…':'');
  if(!job.result){$('sales-result').hidden=true;$('approval-panel').hidden=true;return;}
  const result=job.result;$('sales-result').hidden=false;text('job-status',labels[result.business_status]);
  $('metrics').replaceChildren();
  if(result.report){metric('销售额 / 元',result.report.total_yuan);metric('已支付订单',result.report.order_count);metric('展示明细',result.report.rows_returned);}
  text('sales-answer',result.answer);text('sales-source',`执行 ${job.source_ids.run_id} · 原任务 ${job.source_ids.task_id}\n${result.report?.truncated?'金额为全量合计，明细仅展示部分。':''}`);
  text('sales-receipt',result.receipt?JSON.stringify(result.receipt,null,2):'未调用工具，未产生回执。');
  text('sales-events',JSON.stringify(result.events,null,2));
  const approvalId=job.source_ids.approval_id;
  if(approvalId)await loadApproval(approvalId,id);else{$('approval-panel').hidden=true;proposal=null;}
}
async function loadApproval(id=current?.source_ids.approval_id, job=selected) {
  if(!id)return;const data=await request(`/approvals/${encodeURIComponent(id)}`);if(selected!==job)return;
  proposal=data;$('approval-panel').hidden=false;text('approval-status',`${labels[data.effective_status] || data.effective_status} · external_send: false`);
  $('approval-meta').replaceChildren();
  for(const [name,value] of [['收件对象',data.proposal.recipient],['提案编号',data.approval_id],['版本',data.revision],['有效期至',date(data.expires_at)],['摘要',data.digest],['来源',data.proposal.agent_run_id+'/T1']]){const dt=document.createElement('dt');dt.textContent=name;const dd=document.createElement('dd');dd.textContent=value;$('approval-meta').append(dt,dd);}
  text('proposal-body',data.proposal.body);const disabled=data.effective_status!=='pending';$('review-approve').disabled=disabled;$('review-reject').disabled=disabled;
  $('outbox').replaceChildren();
  if(!data.simulated_messages.length){const p=document.createElement('p');p.className='hint';p.textContent='暂无模拟发送记录。';$('outbox').append(p);}
  for(const entry of data.simulated_messages){const div=document.createElement('div');div.className='outbox-item';div.textContent=`已模拟发送 1 次 · ${date(entry.created_at)}\n收件对象：${entry.recipient}\n${entry.body}\nexternal_send: false`;$('outbox').append(div);}
}
$('approval-refresh').addEventListener('click',()=>loadApproval().catch(showError));
async function openReview(decision) {
  if(!proposal)return;const job=selected;const id=proposal.approval_id;
  try {
    await loadApproval(id,job);if(job!==selected||proposal.approval_id!==id)return;
    if(proposal.effective_status!=='pending')throw new Error('提案已不可审批，请查看当前状态。');
    review={snapshot:proposal,decision,key:crypto.randomUUID()};
    text('review-title',decision==='approve'?'审阅并批准本地模拟发送':'确认拒绝提案');
    text('review-meta',`收件对象：${proposal.proposal.recipient}\n版本 ${proposal.revision} · 有效期至 ${date(proposal.expires_at)}\n来源：${proposal.proposal.agent_run_id}/T1\n摘要：${proposal.digest}`);
    text('review-body',proposal.proposal.body);text('review-error','');$('review-check').checked=false;$('confirm-decision').disabled=true;
    $('confirm-decision').textContent=decision==='approve'?'确认批准并模拟发送':'确认拒绝';
    $('reason-label').hidden=decision==='approve';$('reject-reason').hidden=decision==='approve';$('reject-reason').value='not_needed';
    $('review-dialog').showModal();
  }catch(e){showError(e);}
}
$('review-approve').addEventListener('click',()=>openReview('approve'));
$('review-reject').addEventListener('click',()=>openReview('reject'));
$('review-check').addEventListener('change',()=>{$('confirm-decision').disabled=!$('review-check').checked;});
$('cancel-decision').addEventListener('click',()=>{$('review-dialog').close();review=null;});
$('confirm-decision').addEventListener('click',async()=>{
  if(!review||!$('review-check').checked||$('confirm-decision').disabled)return;
  $('confirm-decision').disabled=true;$('cancel-decision').disabled=true;$('review-check').disabled=true;
  const action=review;const old=action.snapshot;
  try {
    const fresh=await request(`/approvals/${old.approval_id}`);
    if(fresh.digest!==old.digest||fresh.revision!==old.revision)throw new Error('提案内容已变化，请取消并重新审阅。');
    // A lost successful response can be retried with the same key. Terminal
    // states are still decided by the server; never silently change the action.
    const body=action.body ||= {decision:action.decision,digest:old.digest,revision:old.revision,confirm:action.decision.toUpperCase(),reason:$('reject-reason').value};
    const result=await post(`/approvals/${old.approval_id}/decisions`,body,action.key);
    text('decision-state',labels[result.decision_result]||result.decision_result);$('review-dialog').close();review=null;
    await loadApproval(old.approval_id,old.job_id);
  }catch(e){text('review-error',e.message);await loadApproval(old.approval_id,old.job_id).catch(showError);}
  finally{$('cancel-decision').disabled=false;$('review-check').disabled=false;$('confirm-decision').disabled=!$('review-check').checked;}
});
async function tick(){if(polling)return;polling=true;try{
  const health=await request('/console/worker');text('worker-state',({healthy:'● 执行器在线',stale:'执行器心跳过期，请检查服务',missing:'执行器尚未启动，任务会排队',stopped:'执行器已停止，任务会排队'}[health.status]));
  await loadJob();
  if(pollError && $('console-error').textContent===pollError)text('console-error','');
  pollError='';
}catch(e){pollError=e.message;showError(e);}finally{polling=false;}}
async function init(){try{
  const capabilities=await request('/console/capabilities');if(!capabilities.agent_runs_available)throw new Error('当前部署未启用销售页面，请启动 compose.console.yaml。');
  cases=capabilities.sales_cases;for(const item of cases){const option=document.createElement('option');option.value=item.id;option.textContent=item.label;$('sales-case').append(option);}
  if(pending)$('sales-case').value=pending.case;scope();controls();
  const id=new URL(location.href).searchParams.get('job')||pending?.job_id;if(id&&/^[0-9a-f]{32}$/.test(id))selectJob(id);
  await loadHistory();await tick();setInterval(tick,1500);
}catch(e){showError(e);}}
void init();
