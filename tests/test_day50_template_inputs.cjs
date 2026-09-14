// Offline sample compatibility only: no n8n runtime, API calls or model execution.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
const read = file => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
const catalog = read('n8n/templates/catalog.json');
const now = {toISO: () => '2026-09-14T00:00:00+08:00', toISODate: () => '2026-09-14'};
function normalizeSet(node, body) {
  const input = {body, query: {}, headers: {}};
  return Object.fromEntries(node.parameters.assignments.assignments.map(a => {
    const value = typeof a.value === 'string' && a.value.startsWith('={{')
      ? new Function('$json', '$execution', '$now', `return (${a.value.slice(3, -2)});`)(input, {mode: 'test'}, now)
      : a.value;
    return [a.name, value];
  }));
}
let count = 0;
for (const template of catalog.templates) {
  const workflow = read(template.workflow);
  const node = name => workflow.nodes.find(n => n.name === name);
  for (const example of template.examples) {
    const body = read(example.file);
    if (template.id === 'sales-followup') {
      const result = new Function('$input', node('Normalize Sales Lead').parameters.jsCode)({first: () => ({json: {body}})})[0].json;
      assert.equal(result.input_valid, true, example.file);
      assert.equal(result.event_id, body.event_id);
    } else if (template.id === 'email-assistant') {
      const input = normalizeSet(node('Normalize Email Request'), body);
      const result = new Function('items', node('Classify Email Request').parameters.jsCode)([{json: input}])[0].json;
      assert.equal(result.accepted, true, example.file);
      assert.equal(result.need_human_review, example.scenario === 'human-review', example.file);
    } else {
      const result = normalizeSet(node('Normalize Request'), body);
      assert.equal(result.message, body.message);
      assert.equal(result.customer_id, body.customer_id);
      assert.equal(result.request_id, body.request_id);
    }
    count++;
  }
}
console.log(`${count} new template examples passed offline input compatibility checks. No model outputs or end-to-end behavior tested.`);
