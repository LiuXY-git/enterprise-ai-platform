// UI-only regression: static frontend + explicitly fixed local API responses.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..');
const fixtures=JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/console-browser.json'),'utf8')).cases;
const cases=[['monthly','月度汇总','2026 年 9 月 · 所有客户'],['customer','客户汇总','2026 年 9 月 · C001'],['empty','无数据','2026 年 7 月 · 所有客户'],['clarification','缺少条件','未指定年月']].map(([id,label,scope])=>({id,label,scope}));
function createServer(){
 const jobs=[], keys=new Map(),approvals=new Map(),decisionKeys=new Map();
 return http.createServer(async(req,res)=>{try{
  const url=new URL(req.url,'http://localhost');const p=url.pathname;const chunks=[];for await(const c of req)chunks.push(c);
  const raw=Buffer.concat(chunks).toString();
  function send(value,status=200){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));}
  if(p==='/api/console/capabilities')return send({agent_runs_available:true,sales_cases:cases});
  if(p==='/api/console/worker')return send({status:'healthy'});
  if(p==='/api/health')return send({status:'ok'});
  if(p==='/api/upload')return send({status:'indexed',filename:'nebula-it-policy.md',document_id:1,chunk_count:1});
  if(p==='/api/rag/query')return send({results:[{source:'nebula-it-policy.md',chunk_index:0,text:'P1 级故障应在 15 分钟内响应。浏览器固定测试响应。<img src=x onerror=alert(1)>'}]});
  if(p==='/api/agent-runs'&&req.method==='POST'){
   const key=req.headers['idempotency-key'];if(keys.has(key))return send({job:keys.get(key),reused:true},202);
   const body=JSON.parse(raw),fixture=structuredClone(fixtures[body.case]);
   const job={job_id:crypto.randomUUID().replaceAll('-',''),kind:'agent',mode:'fixture',input:{case:body.case},status:'succeeded',stage:'succeeded',created_at:new Date().toISOString(),finished_at:new Date().toISOString(),error:null,result:fixture.result,source_ids:fixture.result.source_ids};
   if(fixture.approval){const a=fixture.approval;a.job_id=job.job_id;a.expires_at=new Date(Date.now()+1800000).toISOString();a.simulated_messages=[];approvals.set(a.approval_id,a);}
   jobs.unshift(job);keys.set(key,job);return send({job,reused:false},202);
  }
  if(p==='/api/jobs')return send({jobs:jobs.slice(Number(url.searchParams.get('offset')),Number(url.searchParams.get('offset'))+8),total:jobs.length});
  if(p.startsWith('/api/jobs/'))return send(jobs.find(j=>j.job_id===p.split('/').at(-1))||{},jobs.some(j=>j.job_id===p.split('/').at(-1))?200:404);
  if(p.startsWith('/api/approvals/')){
   const aid=p.split('/')[3],a=approvals.get(aid);if(!a)return send({},404);
   if(req.method==='POST'){
    const key=req.headers['idempotency-key'];if(decisionKeys.has(key))return send({...a,decision_result:decisionKeys.get(key),reused:true});
    const body=JSON.parse(raw);a.status=a.effective_status=body.decision==='approve'?'executed':'rejected';
    if(body.decision==='approve'){a.simulation_count=1;a.simulated_messages=[{approval_id:aid,recipient:a.proposal.recipient,body:a.proposal.body,created_at:new Date().toISOString(),external_send:false}];}
    decisionKeys.set(key,a.status);return send({...a,decision_result:a.status,reused:false});
   }return send(a);
  }
  const names={'/':'index.html','/sales.html':'sales.html','/workflows.html':'workflows.html','/evaluations.html':'evaluations.html','/styles.css':'styles.css','/console.css':'console.css','/sales.js':'sales.js','/console-api.js':'console-api.js','/app.js':'app.js'};
  const name=names[p];if(!name){res.writeHead(404);return res.end();}
  res.writeHead(200,{'Content-Type':name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html; charset=utf-8'});res.end(fs.readFileSync(path.join(root,'frontend/public',name)));
 }catch(error){res.writeHead(500);res.end('{}');console.error(error);}});
}
module.exports={createServer};
