const {test} = require('node:test');
const assert = require('node:assert/strict');
const {INSTALL_NETWORK_POLICY, createPrecacheNetworkPlugin} = require('../build-pwa.cjs');

function harness(overrides = {}, responses = []) {
  const messages = [];
  let calls = 0;
  const env = {performance, setTimeout, clearTimeout, Request, URL, AbortController, Date,
    location: {origin: 'https://fixture.test'},
    clients: {async matchAll() {return [{postMessage(message) {messages.push({...message, at: performance.now()});}}];}},
    async fetch(request) {calls++; assert(!request.signal.aborted); return responses.shift() || new Response('ok');},
  };
  const policy = {...INSTALL_NETWORK_POLICY, minIntervalMs: 20, backoffMs: [20, 40, 80], requestTimeoutMs: 1000, ...overrides};
  const plugin = createPrecacheNetworkPlugin(policy, env);
  const params = () => ({request: new Request('https://fixture.test/resource.js'), event: {type: 'install'}, state: {}});
  return {plugin, params, messages, policy, calls: () => calls};
}

test('throttling touches only same-origin install GETs', async () => {
  const h = harness();
  for (const [url, method, type] of [['https://elsewhere.test/a', 'GET', 'install'],
    ['https://fixture.test/a', 'POST', 'install'], ['https://fixture.test/a', 'GET', 'fetch']]) {
    const request = new Request(url, {method});
    const state = {};
    assert.equal(await h.plugin.requestWillFetch({request, state, event: {type}}), request);
    assert.equal(state.originalRequest, undefined);
  }
  assert.equal(h.messages.length, 0);
});

test('separate manifest fetch starts retain a minimum interval', async () => {
  const h = harness({minIntervalMs: 45});
  for (let i = 0; i < 2; i++) {
    const p = h.params();
    await h.plugin.requestWillFetch(p);
    await h.plugin.fetchDidSucceed({...p, response: new Response('ok')});
    await h.plugin.cacheDidUpdate(p);
  }
  const starts = h.messages.filter((e) => e.stage === 'start');
  assert.equal(starts.length, 2);
  assert(starts[1].at - starts[0].at >= 43);
});

test('429 and temporary 503 recover with bounded attempts and an eventual real response', async () => {
  const h = harness({}, [new Response('busy', {status: 503}), new Response('restored')]);
  const p = h.params();
  await h.plugin.requestWillFetch(p);
  const result = await h.plugin.fetchDidSucceed({...p, response: new Response('rate limited', {status: 429})});
  assert.equal(result.status, 200);
  assert.equal(await result.text(), 'restored');
  assert.equal(h.calls(), 2);
  assert.equal(p.state.attempt, 3);
  assert.deepEqual(h.messages.filter((e) => e.stage === 'retry').map((e) => e.wait_ms), [20, 40]);
  await h.plugin.cacheDidUpdate(p);
});

test('exhausted retries return the error for Workbox rejection instead of fabricating a response', async () => {
  const h = harness({}, Array.from({length: 3}, () => new Response('busy', {status: 429})));
  const p = h.params();
  await h.plugin.requestWillFetch(p);
  const result = await h.plugin.fetchDidSucceed({...p, response: new Response('busy', {status: 429})});
  assert.equal(result.status, 429);
  assert.equal(p.state.attempt, 4);
  assert.equal(h.calls(), 3);
  assert(h.messages.some((e) => e.reason === 'retries_exhausted'));
});

test('Retry-After seconds and HTTP dates are honored; excessive delay stops boundedly', async () => {
  for (const retryAfter of ['0.08', new Date(Date.now() + 1600).toUTCString()]) {
    const h = harness();
    const p = h.params();
    await h.plugin.requestWillFetch(p);
    await h.plugin.fetchDidSucceed({...p, response: new Response('busy', {status: 429, headers: {'Retry-After': retryAfter}})});
    const retry = h.messages.find((e) => e.stage === 'retry');
    assert(retry.wait_ms >= retry.retry_after_ms);
    const starts = h.messages.filter((e) => e.stage === 'start');
    assert(starts[1].at - starts[0].at >= retry.wait_ms - 3);
    await h.plugin.cacheDidUpdate(p);
  }
  const h = harness();
  const p = h.params();
  await h.plugin.requestWillFetch(p);
  const response = new Response('busy', {status: 429, headers: {'Retry-After': '120'}});
  assert.equal(await h.plugin.fetchDidSucceed({...p, response}), response);
  assert.equal(h.calls(), 0);
  assert(h.messages.some((e) => e.reason === 'retry_after_exceeds_budget'));
});

test('404 and 501 are not retried', async () => {
  for (const status of [404, 501]) {
    const h = harness();
    const p = h.params();
    await h.plugin.requestWillFetch(p);
    const response = new Response('missing', {status});
    assert.equal(await h.plugin.fetchDidSucceed({...p, response}), response);
    assert.equal(h.calls(), 0);
    await h.plugin.handlerDidComplete({...p, error: new Error('Workbox rejected error status')});
  }
});

test('abort deadline remains alive after response headers and rejects a late cache write', async () => {
  const h = harness({requestTimeoutMs: 40});
  const p = h.params();
  const request = await h.plugin.requestWillFetch(p);
  await h.plugin.fetchDidSucceed({...p, response: new Response('headers arrived')});
  assert(!request.signal.aborted);
  await new Promise((resolve) => setTimeout(resolve, 65));
  assert(request.signal.aborted);
  await assert.rejects(h.plugin.cacheDidUpdate(p), /body\/cache write/);
});

test('install budget cannot be extended by backoff', async () => {
  const h = harness({installBudgetMs: 30, backoffMs: [100, 200, 400]});
  const p = h.params();
  await h.plugin.requestWillFetch(p);
  await assert.rejects(h.plugin.fetchDidSucceed({...p, response: new Response('busy', {status: 429})}), /bounded network budget/);
  await h.plugin.handlerDidComplete({...p, error: new Error('budget exceeded')});
  assert.equal(h.calls(), 0);
});
