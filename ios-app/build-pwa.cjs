const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {getManifest} = require('workbox-build');

const INSTALL_NETWORK_POLICY = Object.freeze({
  version: 1,
  minIntervalMs: 800,
  maxRetries: 3,
  backoffMs: [2000, 4000, 8000],
  maxRetryAfterMs: 30000,
  requestTimeoutMs: 15000,
  installBudgetMs: 330000,
});

// Bundled only into the worker, not the app or the native bundle.
// Public hooks: https://developer.chrome.com/docs/workbox/using-plugins
// addPlugins: https://developer.chrome.com/docs/workbox/modules/workbox-precaching
function createPrecacheNetworkPlugin(policy, env = globalThis) {
  let firstStart = null;
  let lastStart = -Infinity;
  let gate = Promise.resolve();
  const now = () => env.performance.now();
  const sleep = (ms) => new Promise((resolve) => env.setTimeout(resolve, ms));
  const isInstall = (event, request) => event?.type === 'install'
    && request.method === 'GET' && new env.URL(request.url).origin === env.location.origin;
  const transient = (status) => [429, 500, 502, 503, 504].includes(status);
  const remaining = () => firstStart === null ? policy.installBudgetMs : policy.installBudgetMs - (now() - firstStart);
  const assertBudget = (wait = 0) => {
    if (remaining() <= wait) throw new Error('Precache install exceeded its bounded network budget');
  };
  async function notify(state, stage, details = {}) {
    const message = {type: 'XY_PRECACHE_NETWORK', policy_version: policy.version, stage,
      url: state.originalRequest.url, attempt: state.attempt,
      elapsed_ms: Math.round(firstStart === null ? 0 : now() - firstStart), ...details};
    const windows = await env.clients.matchAll({type: 'window', includeUncontrolled: true});
    for (const client of windows) client.postMessage(message);
  }
  function clearTimer(state) {
    if (state.timeout !== undefined) env.clearTimeout(state.timeout);
    state.timeout = undefined;
  }
  async function startAttempt(state) {
    const scheduled = gate.then(async () => {
      const delay = Math.max(0, lastStart + policy.minIntervalMs - now());
      assertBudget(delay);
      if (delay) await sleep(delay);
      assertBudget();
      if (firstStart === null) firstStart = now();
      lastStart = now();
      state.attempt += 1;
      state.controller = new env.AbortController();
      const limit = Math.min(policy.requestTimeoutMs, remaining());
      state.timeout = env.setTimeout(() => {
        state.controller.abort();
        void notify(state, 'timeout', {timeout_ms: Math.round(limit)}).catch(() => {});
      }, limit);
      await notify(state, 'start', {minimum_interval_ms: policy.minIntervalMs});
      return new env.Request(state.originalRequest, {signal: state.controller.signal});
    });
    gate = scheduled.then(() => {}, () => {});
    return scheduled;
  }
  function retryAfterMs(response) {
    const raw = response.headers.get('retry-after');
    if (raw === null) return 0;
    if (/^\d+(?:\.\d+)?$/.test(raw.trim())) return Number(raw) * 1000;
    const date = Date.parse(raw);
    return Number.isFinite(date) ? Math.max(0, date - env.Date.now()) : 0;
  }
  return {
    async requestWillFetch({request, event, state}) {
      if (!isInstall(event, request)) return request;
      state.originalRequest = request.clone();
      state.attempt = 0;
      return startAttempt(state);
    },
    async fetchDidSucceed({response, state}) {
      if (!state.originalRequest) return response;
      let current = response;
      while (true) {
        await notify(state, 'response', {status: current.status});
        if (!transient(current.status)) return current;
        const requestedWait = retryAfterMs(current);
        if (state.attempt > policy.maxRetries || requestedWait > policy.maxRetryAfterMs) {
          clearTimer(state);
          await notify(state, 'failed', {status: current.status,
            reason: requestedWait > policy.maxRetryAfterMs ? 'retry_after_exceeds_budget' : 'retries_exhausted'});
          return current;
        }
        const delay = Math.max(requestedWait, policy.backoffMs[state.attempt - 1]);
        assertBudget(delay);
        clearTimer(state);
        if (current.body) await current.body.cancel();
        await notify(state, 'retry', {status: current.status, wait_ms: delay, retry_after_ms: requestedWait});
        await sleep(delay);
        const request = await startAttempt(state);
        try {
          current = await env.fetch(request);
        } catch (error) {
          clearTimer(state);
          await notify(state, 'failed', {reason: state.controller.signal.aborted ? 'request_timeout' : 'network_error'});
          throw error;
        }
      }
    },
    async fetchDidFail({state}) {
      if (!state.originalRequest) return;
      clearTimer(state);
      await notify(state, 'failed', {reason: state.controller.signal.aborted ? 'request_timeout' : 'network_error'});
    },
    async cacheDidUpdate({state}) {
      if (!state.originalRequest) return;
      // Keep abort alive through body consumption and CacheStorage.put, not just headers.
      const aborted = state.controller.signal.aborted;
      clearTimer(state);
      assertBudget();
      if (aborted) throw new Error('Precache body/cache write exceeded its bounded request deadline');
      await notify(state, 'cached', {status: 200});
    },
    async handlerDidComplete({state, error}) {
      if (!state.originalRequest) return;
      clearTimer(state);
      if (error) await notify(state, 'failed', {reason: 'workbox_handler_failed'});
    },
  };
}

async function buildPwa(dist = path.join(__dirname, 'dist')) {
  const {rollup} = require('rollup');
  const {nodeResolve} = require('@rollup/plugin-node-resolve');
  const replace = require('@rollup/plugin-replace');
  const {babel} = require('@rollup/plugin-babel');
  const presetEnv = require('@babel/preset-env');
  const terser = require('@rollup/plugin-terser');
  const result = await getManifest({globDirectory: dist,
    globPatterns: ['**/*.{html,js,css,png,ico,ttf,woff,woff2,json,webmanifest}'],
    globIgnores: ['**/*.map', 'sw.js', 'workbox-*.js'], maximumFileSizeToCacheInBytes: 5 * 1024 * 1024});
  if (result.warnings.length) throw Error(result.warnings.join('\n'));
  const entries = result.manifestEntries.map(({url, revision}) => ({url, revision}));
  const entryId = path.join(__dirname, 'xiaoyuan-generated-pwa-worker.js');
  const worker = `
import {setCacheNameDetails, clientsClaim} from 'workbox-core';
import {addPlugins, precacheAndRoute, cleanupOutdatedCaches, createHandlerBoundToURL} from 'workbox-precaching';
import {registerRoute, NavigationRoute} from 'workbox-routing';
setCacheNameDetails({prefix: 'xiaoyuan-original'});
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});
clientsClaim();
addPlugins([(${createPrecacheNetworkPlugin.toString()})(${JSON.stringify(INSTALL_NETWORK_POLICY)})]);
precacheAndRoute(${JSON.stringify(entries)});
cleanupOutdatedCaches();
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), {
  denylist: [/^\\/(?:api|_eas)\\//, /\\.(?:js|css|png|json|webmanifest|ico|ttf|woff2?)$/]
}));
`;
  const bundle = await rollup({input: entryId, plugins: [
    {name: 'xiaoyuan-pwa-entry', resolveId(id) {if (id === entryId) return entryId;}, load(id) {if (id === entryId) return worker;}},
    nodeResolve(), replace({preventAssignment: true, 'process.env.NODE_ENV': JSON.stringify('production')}),
    babel({babelHelpers: 'bundled', babelrc: false, configFile: false,
      presets: [[presetEnv, {targets: {browsers: ['chrome >= 56']}, loose: true}]]}),
    terser(),
  ]});
  let output;
  try {({output} = await bundle.generate({format: 'iife', sourcemap: false}));}
  finally {await bundle.close();}
  if (output.length !== 1 || output[0].type !== 'chunk') throw Error('Expected one self-contained PWA worker');
  const license = fs.readFileSync(path.join(__dirname, 'node_modules/workbox-core/LICENSE'), 'utf8');
  const body = `/*! Workbox ${require('workbox-core/package.json').version}; bundled locally.\n${license}\n*/\n` + output[0].code;
  const target = path.join(dist, 'sw.js');
  fs.writeFileSync(target + '.tmp', body);
  fs.renameSync(target + '.tmp', target);
  for (const name of fs.readdirSync(dist)) {
    if (!/^workbox-[a-f0-9]+\.js$/.test(name)) continue;
    const obsolete = path.resolve(dist, name);
    if (path.dirname(obsolete) !== path.resolve(dist)) throw Error('Runtime cleanup escaped dist');
    fs.unlinkSync(obsolete);
  }
  const bank = require('./src/content/original-bank.json');
  const report = {version: require('./package.json').version, bank_id: bank.id, bank_fingerprint: bank.fingerprint,
    question_count: Object.keys(bank.questions).length, cached_files: result.count, cached_bytes: result.size,
    progress_in_cache: false, automatic_mid_challenge_reload: false, workbox_runtime: 'inlined',
    precache_network_policy: INSTALL_NETWORK_POLICY, sw_sha256: crypto.createHash('sha256').update(body).digest('hex')};
  const qa = path.join(__dirname, '../.qa/pwa');
  fs.mkdirSync(qa, {recursive: true});
  fs.writeFileSync(path.join(qa, 'pwa-build.json'), JSON.stringify(report, null, 2) + '\n');
  return report;
}

module.exports = {INSTALL_NETWORK_POLICY, createPrecacheNetworkPlugin, buildPwa};
if (require.main === module) buildPwa().then((report) => {
  process.stdout.write(JSON.stringify(report) + '\n');
}).catch((error) => {console.error(error); process.exitCode = 1;});
