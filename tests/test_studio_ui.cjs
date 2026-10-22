'use strict';
// No browser, network, package install or customer files required.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/studio-utils.js'), 'utf8'), context);
const counts = log => JSON.parse(JSON.stringify(context.runCounts(log)));

test('active item is remaining, but is not waiting or a new error', () => {
  const result = counts({planned_items: 4, events: [
    {type: 'item_start', id: '30'},
    {type: 'item_end', id: '30', status: 'CONCLUIDO'},
    {type: 'item_start', id: '40'},
  ]});
  assert.deepEqual(result, {planned: 4, started: 2, completed: 1, errors: 0, review: 0,
    waiting: 2, remaining: 3});
});

test('review is separate from errors and duplicate events count once per ID', () => {
  const result = counts({planned_items: 3, events: [
    {type: 'item_start', id: '1'}, {type: 'item_start', id: '1'},
    {type: 'item_end', id: '1', status: 'ERRO'},
    {type: 'item_end', id: '1', status: 'ERRO'},
    {type: 'item_end', id: '2', status: 'REVISAO'},
  ]});
  assert.equal(result.errors, 1);
  assert.equal(result.review, 1);
  assert.equal(result.started, 2);
  assert.equal(result.waiting, 1);
  assert.equal(result.remaining, 1);
});

test('legacy summaries and empty state remain readable', () => {
  assert.equal(counts(null).remaining, 0);
  const result = counts({planned_items: 5, result: {processed: 3, success: 1, errors: 1, review: 1}});
  assert.equal(result.completed, 1);
  assert.equal(result.errors, 1);
  assert.equal(result.review, 1);
  assert.equal(result.remaining, 2);
  assert.equal(context.formatDuration(119.5), '2 min');
  assert.equal(context.formatDuration(null), '—');
});
