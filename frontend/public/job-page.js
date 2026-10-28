import {$,text,request,post,labels,date} from './console-api.js';
export const element=(tag, value, cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};
export function detail(parent, title, data){const d=element('details');d.append(element('summary',title),element('pre',JSON.stringify(data,null,2)));parent.append(d);}
export function metric(parent, title, value){const e=element('div',undefined,'metric');e.append(element('strong',value??'未知'),element('span',title));parent.append(e);}
export async function startPage({kind,endpoint,ready,body,render}){
  const storageKey=`eap-${kind}-submission-v1`;let selected=new URL(location.href).searchParams.get('job');let offset=0,busy=false,stopped=false;
  const historyButtons=new Map();let lastRendered=null;let pollError='';let saved=null;try{saved=JSON.parse(localStorage.getItem(storageKey));}catch{}
  function save(value){saved=value;try{localStorage.setItem(storageKey,JSON.stringify(value));}catch{}}
  function error(e){text('console-error',e.message);}
  function choose(job){selected=job.job_id;const url=new URL(location.href);url.searchParams.set('job',selected);history.replaceState(null,'',url);show(job);}
  function show(job){
    for(const [id,button] of historyButtons){button.classList.toggle('active',id===job.job_id);if(id===job.job_id)button.firstChild.nodeValue=`${job.input.template_id||job.input.suite} · ${labels[job.status]||job.status}`;}
    text('job-title',`${kind==='workflow'?'工作流':'评测'} · ${labels[job.status]||job.status}`);
    text('job-meta',`任务 ${job.job_id}
模式 ${job.mode} · 创建 ${date(job.created_at)}
阶段 ${job.stage}`);
    text('job-status',job.error?`${labels[job.status]}：${({configuration_missing:'尚未配置 n8n，未发送请求。',workflow_outcome_unknown:'外部结果待核对，请按事件编号在 n8n 查询，不要盲目重跑。',task_timeout:'执行超时，保留已有进度与证据。',worker_interrupted:'执行器停止，任务未自动重跑。',worker_lease_expired:'执行器失联，需核对任务。'}[job.error.code]||'执行异常，请检查服务日志。')}`:(labels[job.status]||job.status));
    const p=job.progress||{};const evalJob=kind==='evaluation';$('job-progress').hidden=!evalJob;
    if(evalJob){const total=p.selected||(job.input.suite==='full'?12:4);$('job-progress').value=job.status==='succeeded'&&p.graded&&p.completed===total&&!job.result?.summary?.not_evaluated?100:Math.min(99,100*(p.completed||0)/total);text('progress-caption',`${p.completed||0} / ${total} 例已执行${p.active_case?' · 当前 '+p.active_case:''}${p.graded?' · 评分已生成':' · 评分尚未完成'}`);}
    else text('progress-caption',p.event_id?`事件编号 ${p.event_id} · 不自动重放${job.mode==='live'&&['failed','interrupted'].includes(job.status)?' · 请先到 n8n 核对外部结果':''}`: '');
    const fingerprint=JSON.stringify([job.job_id,job.result]);if(fingerprint!==lastRendered){lastRendered=fingerprint;$('task-result').replaceChildren();$('task-result').hidden=!job.result;if(job.result)render($('task-result'),job.result,job);}
  }
  async function historyList(){const data=await request(`/jobs?kind=${kind}&limit=8&offset=${offset}`);text('history-state',`共 ${data.total} 条 · 第 ${Math.floor(offset/8)+1} 页`);$('history-list').replaceChildren();historyButtons.clear();for(const job of data.jobs){const button=element('button',`${job.input.template_id||job.input.suite} · ${labels[job.status]||job.status}`,'history-item');button.type='button';historyButtons.set(job.job_id,button);button.classList.toggle('active',job.job_id===selected);button.append(element('small',`${job.mode} · ${date(job.created_at)} · ${job.job_id.slice(0,8)}`));button.addEventListener('click',()=>choose(job));$('history-list').append(button);}$('previous').disabled=offset===0;$('next').disabled=offset+8>=data.total;}
  $('task-form').addEventListener('submit',async event=>{event.preventDefault();if(busy)return;busy=true;$('submit-task').disabled=true;try{const value=body();const encoded=JSON.stringify(value);if(saved&&saved.body!==encoded)throw new Error('输入已变化，请点“新建一份”后提交；原请求仍可从历史核对。');if(!saved)save({key:crypto.randomUUID(),body:encoded});const data=await post(endpoint,value,saved.key);choose(data.job);text('submit-state',data.reused?'已返回原任务，没有重复执行。':'已入队，关闭页面不影响后台运行。');text('console-error','');await historyList();}catch(e){error(e);}finally{busy=false;$('submit-task').disabled=false;}});
  $('new-task').addEventListener('click',()=>{save(null);text('submit-state','已准备新的提交编号，请核对输入后执行。');text('console-error','');});
  $('history-refresh').addEventListener('click',()=>historyList().catch(error));
  for(const [id,delta] of [['previous',-8],['next',8]])$(id).addEventListener('click',()=>{offset=Math.max(0,offset+delta);historyList().catch(error);});
  async function poll(){if(stopped)return;try{const worker=await request('/console/worker');text('worker-state',worker.status==='healthy'?'执行器在线':`执行器 ${worker.status} · 任务可能停留在队列`);if(selected){const id=selected;const job=await request('/jobs/'+encodeURIComponent(id));if(id!==selected)return;if(job.kind!==kind)throw new Error('任务不属于当前模块');show(job);}if(pollError&&$('console-error').textContent===pollError)text('console-error','');pollError='';}catch(e){pollError=e.message;error(e);}finally{if(!stopped)setTimeout(poll,1500);}}
  addEventListener('pagehide',()=>{stopped=true;});
  try{const caps=await request('/console/capabilities');if(!caps[kind==='workflow'?'workflow_execution_available':'evaluation_runs_available'])throw new Error('请启动第 4、5 天控制台服务。');ready(caps);$('submit-task').disabled=false;await historyList();poll();}catch(e){error(e);}
}
