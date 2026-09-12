const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n/workflows/w7d47-sales-followup-assistant.json'), 'utf8'));
const code = workflow.nodes.find(n => n.name === 'Classify AI Failure').parameters.jsCode;
const context = { workflow_run_id: 'test-run', event_id: 'test-event', customer_id: 'test-customer' };
const cases = [
  ['business budget', {error: 'ai_output_validation: invalid fields', output: {summary: 'Budget is 500'}}, true],
  ['business service keywords', {error: 'Failed to parse output', requirement: 'network timeout 401 403 429 503'}, true],
  ['nested parser error', {error: {name: 'NodeOperationError', cause: {message: 'Model output does not fit required format'}}}, true],
  ['quoted output numbers', {error: {message: 'Failed to parse output: Budget is 500; network'}}, true],
  ['invalid JSON', {error: {message: 'Invalid JSON'}}, true],
  ['auth failure', {error: {message: '401 Unauthorized'}, output: {summary: 'schema'}}, false],
  ['rate limit', {error: {statusCode: 429, message: 'Rate limit exceeded'}}, false],
  ['service failure', {error: {message: '503 Service unavailable'}, requirement: 'invalid json'}, false],
  ['timeout', {error: {cause: {code: 'ETIMEDOUT'}}}, false],
  ['raw response excluded', {error: {message: 'Service unavailable', response: {body: 'schema'}}}, false],
  ['unknown error', {error: 'Unknown failure'}, false],
  ['missing error', {output: {summary: 'invalid json schema'}}, false],
];
for (const [name, input, review] of cases) {
  const result = new Function('$input', '$', code)(
    {first: () => ({json: input})}, () => ({first: () => ({json: context})}),
  )[0].json;
  assert.equal(result.requires_human_review, review, name);
  assert.equal(result.error_type, review ? 'ai_output_invalid' : 'ai_service_unavailable', name);
  assert.equal(result.run_id, context.workflow_run_id, name);
  assert.equal(result.event_id, context.event_id, name);
  assert.equal(result.customer_id, context.customer_id, name);
}
console.log(`${cases.length} classification regression cases passed.`);

const checkpoint = {run_id: 'test-run', customer: {customer_id: 'test-customer'}, analysis: {summary: 'approved'}};
const restoreCode = workflow.nodes.find(n => n.name === 'Restore CRM Checkpoint').parameters.jsCode;
const restore = input => new Function('$input', restoreCode)({first: () => ({json: input})})[0].json;
const expression = workflow.nodes.find(n => n.name === 'Save CRM Follow-up').parameters.jsonBody;
const saveBody = input => new Function('$json', `return (${expression.trim().replace(/^=\{\{/, '').replace(/\}\}$/, '')});`)(input);
const restored = restore({workflow_run_id: 'test-run', checkpoint_data: checkpoint});
assert.deepEqual(JSON.parse(saveBody(restored)), checkpoint);
assert.deepEqual(JSON.parse(saveBody({checkpoint_data: checkpoint})), checkpoint);
assert.throws(() => restore({workflow_run_id: 'wrong-run', checkpoint_data: checkpoint}));
assert.throws(() => restore({workflow_run_id: 'test-run', checkpoint_data: null}));
console.log('CRM body and checkpoint ownership regression checks passed.');
