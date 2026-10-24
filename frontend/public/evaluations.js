import {$} from './console-api.js';
import {startPage,element,detail,metric} from './job-page.js';
startPage({kind:'evaluation',endpoint:'/evaluation-runs',ready(){},body(){return {dataset_id:'sales-fixture-v1',agent_id:'day82-candidate',suite:$('suite').value,mode:'fixture'};},render(parent,r,job){
  parent.append(element('span',r.full_dataset_evaluated?'完整测试集 · 12 例':'子集结果 · 不能代表完整测试集','badge'));
  const metrics=element('div',undefined,'metrics');const s=r.summary;for(const [title,value] of [['规则符合率',s.success_rate_percent===null?'未完成':s.success_rate_percent+'%'],['通过 / 分母',`${s.numerator} / ${s.denominator}`],['失败',s.failed],['错误',s.errors],['未评估',s.not_evaluated],['用例累计耗时（ms）',r.latency.sum_case_elapsed_ms]])metric(metrics,title,value);parent.append(metrics);
  parent.append(element('p',`Token：${r.usage.total_tokens??'未知'} · 模型 API 成本：${r.usage.estimated_model_api_cost??'未知'}（fixture，不含本地计算）`,'hint'),element('p',r.notice,'hint'));
  const link=element('a','下载本次 JSON 报告','report-link');link.href=`/api/jobs/${encodeURIComponent(job.job_id)}/report`;link.download=`evaluation-${job.job_id}.json`;parent.append(link);
  parent.append(element('h3','逐例结果与失败原因'));
  for(const row of r.cases){const d=element('details');d.append(element('summary',`${row.case_id} · ${{passed:'通过',failed:'失败',error:'错误',not_evaluated:'未评估'}[row.judgement]}`));d.append(element('p',`执行：${row.execution_status} · 业务：${row.business_status??'未知'} · 耗时：${row.latency_ms??'未知'} ms`,'hint'));d.append(element('p',`原因：${row.reason||row.error||row.failed_rules.join('、')||'符合预期'}。预期拒绝或预期失败也可能评分通过。`));d.append(element('pre',JSON.stringify({checks:row.checks,observed:row.observed,usage:row.usage},null,2)));parent.append(d);}
  detail(parent,'数据集、Agent 与来源版本',{dataset_id:r.dataset_id,dataset_version:r.dataset_version,agent_id:r.agent_id,dataset_sha256:r.dataset_sha256,agent_spec_sha256:r.agent_spec_sha256,source_report_sha256:r.source_report_sha256});detail(parent,'分组与耗时统计',{by_category:r.by_category,latency:r.latency});
}});
