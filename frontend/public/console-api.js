export const $ = (id) => document.getElementById(id);
export const text = (id, value) => { $(id).textContent = value ?? ''; };
export const labels = {queued:'排队中',running:'执行中',succeeded:'执行完成',failed:'执行失败',interrupted:'执行中断',completed:'简报已生成',no_data:'所选范围没有已支付订单',needs_clarification:'需要补充年份和月份',pending:'待人工确认',executed:'已模拟发送',rejected:'已拒绝',expired:'已过期',superseded:'已被新提案替代',digest_mismatch:'摘要不符，请重新审阅',revision_mismatch:'提案版本已变化，请重新审阅',not_pending:'当前状态不能执行此操作',already_executed:'已执行过，未新增发送记录'};
export async function request(path, options={}) {
  const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),10000);
  try {
    const response=await fetch(`/api${path}`,{...options,signal:controller.signal,cache:'no-store'});
    const data=await response.json();
    if(!response.ok) { const e=new Error(labels[data.decision_result] || ({404:'记录不存在',409:'请求冲突，请核对当前状态或重新审阅',422:'输入不符合要求',429:'队列已满，请稍后重试'}[response.status]) || `服务暂不可用（${response.status}）`); e.data=data;throw e; }
    return data;
  } catch(e) { if(e.name==='AbortError') throw new Error('请求超时，结果待核对。重试会沿用本次请求编号。'); if(e instanceof TypeError) throw new Error('连接中断，请检查服务；重试会沿用本次请求编号。'); throw e; }
  finally{clearTimeout(timer);}
}
export const post=(path,body,key)=>request(path,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify(body)});
export const date=(value)=>value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—';
