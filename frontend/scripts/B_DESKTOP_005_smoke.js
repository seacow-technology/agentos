/* eslint-disable no-console */
'use strict';

// B_DESKTOP_005: Playwright smoke for desktop Product Shell + embedded Console routes.
//
// Hard constraints:
// - Do not invent endpoints: this script uses only repo-evidenced routes:
//   - Backend health: GET /api/health (apps/desktop-electron/src/main.ts)
//   - Product shell tabs -> embedded console: /console/*?embed=1 (frontend/reports/commercial_scenario_lock.json,
//     apps/desktop-electron/resources/product-dist/app.js)
// - Proxy server implementation is reused from apps/desktop-electron/dist/proxyServer.js
//
// Modes:
// - boot (default): start backend + proxy, then run Playwright against the proxy URL.
// - running: do not start servers; run Playwright against B_DESKTOP_005_BASE_URL (for an already-running stack).

const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const os = require('node:os');
const { spawn } = require('node:child_process');

const REPO_ROOT = process.cwd();
const EVIDENCE_PATH = path.join(REPO_ROOT, 'frontend', 'reports', 'e2e_endpoint_evidence', 'B_DESKTOP_005.json');

function nowIso() {
  return new Date().toISOString();
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function truncate(s, maxLen) {
  const str = String(s || '');
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + `…(+${str.length - maxLen} chars)`;
}

async function canBindLocalPorts(host) {
  // Some execution environments disallow creating listening sockets entirely (EPERM on listen()).
  // This task’s default "boot" mode requires binding localhost ports for backend + proxy.
  return await new Promise((resolve) => {
    const srv = net.createServer();
    srv.once('error', (err) => resolve({ ok: false, err }));
    srv.listen(0, host, () => {
      srv.close(() => resolve({ ok: true, err: null }));
    });
  });
}

async function findFreePort(host, preferred, span = 64) {
  for (let p = preferred; p < preferred + span; p++) {
    // eslint-disable-next-line no-await-in-loop
    const res = await new Promise((resolve) => {
      const srv = net.createServer();
      srv.once('error', (err) => resolve({ ok: false, err }));
      srv.listen(p, host, () => {
        srv.close(() => resolve({ ok: true, err: null }));
      });
    });
    if (res && res.err && res.err.code === 'EPERM') {
      throw new Error(`BLOCKED: cannot bind local ports in this environment (listen EPERM on ${host}:${p}).`);
    }
    if (res && res.ok) return p;
  }
  // Fallback: ask OS for an ephemeral port to avoid local port collisions.
  const ephemeral = await new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once('error', (err) => {
      if (err && err.code === 'EPERM') {
        reject(new Error(`BLOCKED: cannot bind local ports in this environment (listen EPERM on ${host}:0).`));
      } else {
        reject(err);
      }
    });
    srv.listen(0, host, () => {
      const addr = srv.address();
      const port = addr && typeof addr === 'object' ? addr.port : null;
      srv.close(() => resolve(port));
    });
  });
  if (typeof ephemeral === 'number' && ephemeral > 0) return ephemeral;
  throw new Error(`No free port found near ${preferred}, and ephemeral allocation failed`);
}

async function httpOk(url, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 800);
      // Node 20 has global fetch.
      // eslint-disable-next-line no-undef
      const resp = await fetch(url, { method: 'GET', signal: controller.signal });
      clearTimeout(timer);
      if (resp.ok) return true;
    } catch {
      // ignore
    }
    // eslint-disable-next-line no-await-in-loop
    await sleep(250);
  }
  return false;
}

function spawnLogged(cmd, args, opts, evidence, procKey) {
  const child = spawn(cmd, args, {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    ...opts,
  });
  const stdout = [];
  const stderr = [];
  child.stdout.on('data', (b) => stdout.push(b));
  child.stderr.on('data', (b) => stderr.push(b));

  evidence.processes[procKey] = {
    pid: child.pid,
    cmd: [cmd, ...args].join(' '),
    cwd: opts && opts.cwd ? opts.cwd : undefined,
    started_at: nowIso(),
    stdout_tail: '',
    stderr_tail: '',
  };

  const refreshTails = () => {
    const out = Buffer.concat(stdout).toString('utf8');
    const err = Buffer.concat(stderr).toString('utf8');
    evidence.processes[procKey].stdout_tail = truncate(out.slice(-20_000), 20_000);
    evidence.processes[procKey].stderr_tail = truncate(err.slice(-20_000), 20_000);
  };

  child.on('exit', (code, signal) => {
    refreshTails();
    evidence.processes[procKey].exited = { code, signal, at: nowIso() };
  });

  return { child, refreshTails };
}

async function startBackend(host, preferredPort, ollamaBaseUrl, evidence) {
  const adminToken = process.env.OCTOPUSOS_ADMIN_TOKEN || 'smoke_admin_token';
  const controlToken = process.env.OCTOPUSOS_CONTROL_TOKEN || 'smoke_control_token';

  const port = await findFreePort(host, preferredPort);
  const origin = `http://${host}:${port}`;
  const healthUrl = `${origin}/api/health`;

  // Prefer bundled runtime binary (repo evidence: apps/desktop-electron/binaries/octopusos-runtime exists in this workspace).
  const runtimeBin = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'binaries', process.platform === 'win32' ? 'octopusos-runtime.exe' : 'octopusos-runtime');
  const dataDir = path.join(os.tmpdir(), 'octopusos-smoke', 'B_DESKTOP_005');
  ensureDir(dataDir);

  const commonEnv = {
    ...process.env,
    OCTOPUSOS_ADMIN_TOKEN: adminToken,
    OCTOPUSOS_CONTROL_TOKEN: controlToken,
    OCTOPUSOS_DATA_DIR: dataDir,
    OLLAMA_HOST: ollamaBaseUrl,
  };

  let backendProc = null;
  let backendMode = null;

  if (fs.existsSync(runtimeBin)) {
    backendMode = 'bundled-runtime';
    const args = ['webui', 'start', '--backend-only', '--foreground', '--host', host, '--port', String(port)];
    const started = spawnLogged(runtimeBin, args, { env: commonEnv, cwd: dataDir }, evidence, 'backend');
    backendProc = started.child;
    const ok = await httpOk(healthUrl, 45_000);
    if (!ok) {
      started.refreshTails();
      try { backendProc.kill(); } catch { /* ignore */ }
      backendProc = null;
      backendMode = null;
    }
  }

  if (!backendProc) {
    // Developer fallback (repo evidence: apps/desktop-electron/src/sidecars.ts runs uvicorn octopusos.webui.app:app).
    backendMode = 'uvicorn-source';
    const venvPython = path.join(REPO_ROOT, '.venv', 'bin', 'python');
    const pythonBin = (() => {
      if (fs.existsSync(venvPython)) return venvPython;
      if (process.platform === 'darwin') {
        if (fs.existsSync('/opt/homebrew/bin/python3')) return '/opt/homebrew/bin/python3';
        if (fs.existsSync('/usr/local/bin/python3')) return '/usr/local/bin/python3';
      }
      return 'python3';
    })();
    const args = ['-m', 'uvicorn', 'octopusos.webui.app:app', '--host', host, '--port', String(port)];
    const started = spawnLogged(pythonBin, args, { env: commonEnv, cwd: REPO_ROOT }, evidence, 'backend');
    backendProc = started.child;
    const ok = await httpOk(healthUrl, 45_000);
    if (!ok) {
      started.refreshTails();
      try { backendProc.kill(); } catch { /* ignore */ }
      throw new Error(`Backend did not become healthy within 45s (${healthUrl}). See evidence logs.`);
    }
  }

  evidence.processes.backend.origin = origin;
  evidence.processes.backend.health_url = healthUrl;
  evidence.processes.backend.mode = backendMode;
  evidence.processes.backend.data_dir = dataDir;
  return { origin, port, proc: backendProc, mode: backendMode, healthUrl, dataDir };
}

async function startProxy(host, preferredPort, backendOrigin, evidence) {
  const webuiDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'webui-dist');
  const productDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'product-dist');

  const webuiIndex = path.join(webuiDistDir, 'index.html');
  const productIndex = path.join(productDistDir, 'index.html');

  if (!fs.existsSync(webuiIndex)) {
    throw new Error(`webui dist not found: missing ${webuiIndex}. Run: npm run desktop:electron:sync-webui`);
  }
  if (!fs.existsSync(productIndex)) {
    throw new Error(`product dist not found: missing ${productIndex}`);
  }

  const port = await findFreePort(host, preferredPort);
  // eslint-disable-next-line global-require, import/no-dynamic-require
  const { startWebuiProxyServer } = require(path.join(REPO_ROOT, 'apps', 'desktop-electron', 'dist', 'proxyServer.js'));
  const proxy = await startWebuiProxyServer({
    host,
    port,
    webuiDistDir,
    productDistDir,
    backendOrigin,
  });

  evidence.processes.proxy = {
    url: proxy.url,
    port,
    host,
    webuiDistDir,
    productDistDir,
    backendOrigin,
    started_at: nowIso(),
  };

  return { proxy, url: proxy.url, port };
}

async function runPlaywrightSmoke(baseUrl, evidence) {
  // Load Playwright from a repo-local install. Prefer apps/webui (often has its own node_modules),
  // but fall back to the repo root to avoid BLOCKED in minimal setups.
  // eslint-disable-next-line global-require, import/no-dynamic-require
  const loadPlaywright = () => {
    const candidates = [
      path.join(REPO_ROOT, 'apps', 'webui', 'node_modules', 'playwright'),
      path.join(REPO_ROOT, 'node_modules', 'playwright'),
      'playwright',
    ];
    for (const mod of candidates) {
      try {
        // eslint-disable-next-line global-require, import/no-dynamic-require
        const pw = require(mod);
        return { pw, from: mod };
      } catch {
        // try next
      }
    }
    // eslint-disable-next-line global-require, import/no-dynamic-require
    const pw = require('playwright');
    return { pw, from: 'playwright' };
  };

  const loaded = loadPlaywright();
  const pw = loaded.pw;
  evidence.playwright_module = loaded.from;
  const chromium = pw.chromium;

  // Prefer a persistent Chrome profile so auth state is stable across runs (AGENTS.md).
  // Fall back to an ephemeral context if the profile dir is not writable for some reason.
  let browser = null;
  let context = null;
  let usedPersistentProfile = false;
  const profileDir = String(process.env.PLAYWRIGHT_PROFILE_DIR || '/Users/pangge/.octopusos/playwright-profile').trim();
  try {
    ensureDir(profileDir);
    context = await chromium.launchPersistentContext(profileDir, { headless: true });
    usedPersistentProfile = true;
  } catch (e) {
    evidence.prechecks.push({
      name: 'playwright_persistent_profile_failed',
      dir: profileDir,
      ok: false,
      error: { message: truncate(String(e && e.message ? e.message : e), 2000) },
      at: nowIso(),
    });
    browser = await chromium.launch({ headless: true });
    context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  }
  evidence.playwright_profile = { dir: profileDir, persistent: usedPersistentProfile };

  const page = await context.newPage();

  const consoleEvents = [];
  const pageErrors = [];
  const responses404 = [];
  const requestFailures = [];
  let currentTab = 'unknown';

  page.on('console', (msg) => {
    const entry = { at: nowIso(), type: msg.type(), text: msg.text(), tab: currentTab };
    consoleEvents.push(entry);
  });
  page.on('pageerror', (err) => {
    pageErrors.push({ at: nowIso(), message: String(err && err.message ? err.message : err), tab: currentTab });
  });
  page.on('requestfailed', (req) => {
    requestFailures.push({
      at: nowIso(),
      url: req.url(),
      method: req.method(),
      failure: req.failure() ? req.failure().errorText : 'unknown',
      resourceType: req.resourceType(),
      tab: currentTab,
    });
  });
  page.on('response', (resp) => {
    if (resp.status() === 404) {
      try {
        const u = new URL(resp.url());
        if (u.pathname === '/favicon.ico') return;
      } catch {
        // ignore
      }
      const req = resp.request();
      responses404.push({
        at: nowIso(),
        url: resp.url(),
        status: resp.status(),
        method: req.method(),
        resourceType: req.resourceType(),
        tab: currentTab,
      });
    }
  });

  const checks = [];
  // Do not invent endpoints: this list is derived from Product Shell dist:
  // apps/desktop-electron/resources/product-dist/app.js render() mapping:
  //   /chat -> /console/chat?embed=1
  //   /work -> /console/chat/work?embed=1
  //   /coding -> /console/coding?embed=1
  //   /projects -> /console/projects?embed=1
  //   /aws -> /console/aws?embed=1
  const tabs = [
    { label: 'Chat', hashRoute: '/chat', consolePath: '/chat' },
    { label: 'Work', hashRoute: '/work', consolePath: '/chat/work' },
    { label: 'Coding', hashRoute: '/coding', consolePath: '/coding' },
    { label: 'Projects', hashRoute: '/projects', consolePath: '/projects' },
    { label: 'AWS Ops', hashRoute: '/aws', consolePath: '/aws' },
  ];

  // Sanity check: ensure Product Shell dist still contains these route mappings.
  // If missing, mark BLOCKED rather than "inventing" a route.
  const productAppJs = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'product-dist', 'app.js');
  try {
    const txt = fs.readFileSync(productAppJs, 'utf8');
    const missing = tabs
      .filter((t) => !txt.includes(`if (route === '${t.hashRoute}')`))
      .map((t) => t.hashRoute);
    if (missing.length > 0) {
      throw new Error(`Product Shell dist missing expected routes: ${missing.join(', ')} (${productAppJs})`);
    }
  } catch (e) {
    throw new Error(`BLOCKED: cannot verify Product Shell routes from dist. ${String(e && e.message ? e.message : e)}`);
  }

  const expectedIframeSrc = (consolePath) => `/console${consolePath}?embed=1`;

  const startAt = Date.now();
  const shellResp = await page.goto(`${baseUrl}/#/home`, { waitUntil: 'domcontentloaded', timeout: 45_000 });
  await page.locator('.nav').waitFor({ timeout: 20_000 });

  for (const t of tabs) {
    currentTab = t.label;
    const before404 = responses404.length;
    const beforeConsole = consoleEvents.length;
    const began = Date.now();

    await page.locator('.nav a', { hasText: t.label }).click({ timeout: 15_000 });
    await page.waitForFunction((h) => window.location.hash === `#${h}`, t.hashRoute, { timeout: 15_000 });

    const entry = {
      name: 'product_shell_tab',
      tab: t.label,
      route: `#${t.hashRoute}`,
      ok: false,
      iframe_src: null,
      duration_ms: 0,
      new_404_count: 0,
      new_console_count: 0,
    };

    if (t.consolePath) {
      const iframe = page.locator('iframe.embedFrame');
      await iframe.waitFor({ state: 'visible', timeout: 20_000 });
      const expected = expectedIframeSrc(t.consolePath);
      // Switching tabs updates the iframe src asynchronously; wait for it to settle.
      await page.waitForFunction((exp) => {
        const el = document.querySelector('iframe.embedFrame');
        return !!el && el.getAttribute('src') === exp;
      }, expected, { timeout: 20_000 });

      const src = await iframe.getAttribute('src');
      entry.iframe_src = src;
      if (src !== expected) {
        entry.duration_ms = Date.now() - began;
        entry.ok = false;
        entry.new_404_count = responses404.length - before404;
        entry.new_console_count = consoleEvents.length - beforeConsole;
        checks.push(entry);
        throw new Error(`Unexpected iframe src for ${t.label}: got=${src} expected=${expected}`);
      }

      // Validate the embedded console document itself is not a 404 (avoid false positives from assets).
      // Waiting for the response event is flaky because the iframe navigation may complete
      // before we attach the waiter. Use an explicit request instead.
      const expectedAbs = `${baseUrl}${expected}`;
      const docResp = await page.request.get(expectedAbs);
      entry.iframe_doc = { url: expectedAbs, status: docResp.status() };
      if (docResp.status() === 404) {
        entry.duration_ms = Date.now() - began;
        entry.ok = false;
        entry.new_404_count = responses404.length - before404;
        entry.new_console_count = consoleEvents.length - beforeConsole;
        checks.push(entry);
        throw new Error(`Embedded console document returned 404 for ${t.label}: ${expectedAbs}`);
      }

      // Ensure the embedded WebUI root renders something (not just a blank doc).
      const root = page.frameLocator('iframe.embedFrame').locator('#root');
      await root.waitFor({ state: 'attached', timeout: 20_000 });
      await page.frameLocator('iframe.embedFrame')
        .locator('#root')
        .evaluate((el) => {
          // eslint-disable-next-line no-undef
          return el && el.childNodes && el.childNodes.length > 0;
        }, { timeout: 20_000 });
    } else {
      // Not expected for this smoke; keep for forward compatibility in case tabs list changes.
      await page.locator('.main').waitFor({ timeout: 15_000 });
    }

    // Allow async asset loads to surface 404s/console errors.
    await page.waitForTimeout(750);

    entry.duration_ms = Date.now() - began;
    entry.new_404_count = responses404.length - before404;
    entry.new_console_count = consoleEvents.length - beforeConsole;
    entry.ok = true;
    checks.push(entry);
  }

  evidence.playwright = {
    baseUrl,
    runtime_ms: Date.now() - startAt,
    shell: {
      url: `${baseUrl}/#/home`,
      status: shellResp ? shellResp.status() : null,
    },
    checks,
    console: {
      total: consoleEvents.length,
      errors: consoleEvents.filter((e) => e.type === 'error').slice(-200),
      console_404: consoleEvents
        .filter((e) => e.type === 'error' && /404/i.test(e.text) && !/favicon\\.ico/i.test(e.text))
        .slice(-200),
    },
    page_errors: pageErrors.slice(-200),
    responses_404: responses404.slice(-200),
    request_failures: requestFailures.slice(-200),
  };

  await context.close();
  try { if (browser) await browser.close(); } catch { /* ignore */ }
}

async function main() {
  const mode = (process.env.B_DESKTOP_005_MODE || 'boot').toLowerCase();
  const host = process.env.B_DESKTOP_005_HOST || '127.0.0.1';
  const baseUrlEnv = process.env.B_DESKTOP_005_BASE_URL || `http://${host}:1420`;

  const evidence = {
    task_id: 'B_DESKTOP_005',
    title: 'Playwright smoke for product shell + embedded console',
    started_at: nowIso(),
    ended_at: null,
    status: 'UNKNOWN',
    reason: null,
    env: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
      cwd: process.cwd(),
    },
    config: { mode, host, baseUrl: baseUrlEnv },
    prechecks: [],
    processes: {},
    playwright: null,
  };

  ensureDir(path.dirname(EVIDENCE_PATH));

  let backend = null;
  let proxy = null;
  let proxyHandle = null;

  try {
    if (mode !== 'boot' && mode !== 'running') {
      throw new Error(`Invalid B_DESKTOP_005_MODE=${mode} (expected boot|running)`);
    }

    if (mode === 'boot') {
      const bind = await canBindLocalPorts(host);
      evidence.prechecks.push({
        name: 'can_bind_ports',
        host,
        ok: !!(bind && bind.ok),
        error: bind && bind.err ? { code: bind.err.code, message: String(bind.err.message || bind.err) } : null,
        at: nowIso(),
      });
      if (!bind.ok && bind.err && bind.err.code === 'EPERM') {
        // If we can't bind ports, we can still run the Playwright smoke against an already-running Desktop proxy.
        // This keeps the "single command" UX intact for locked-down environments.
        const reachable = await httpOk(`${baseUrlEnv}/`, 1500);
        evidence.prechecks.push({
          name: 'base_url_reachable_fallback',
          url: baseUrlEnv,
          ok: reachable,
          at: nowIso(),
        });
        if (reachable) {
          evidence.prechecks.push({
            name: 'mode_fallback',
            from: 'boot',
            to: 'running',
            reason: `cannot_bind_ports:${bind.err.code}`,
            at: nowIso(),
          });
          await runPlaywrightSmoke(baseUrlEnv, evidence);
        } else {
          throw new Error(
            `BLOCKED: cannot bind local ports in this environment (listen EPERM on ${host}:0). ` +
            `This smoke’s default mode boots backend + proxy (requires binding localhost ports). ` +
            `Also could not reach B_DESKTOP_005_BASE_URL=${baseUrlEnv}. ` +
            `Start Desktop (proxy at / and Console at /console/) and rerun, or run this smoke on a machine that can bind ports.`
          );
        }
      } else {
        const ollamaBaseUrl = process.env.OLLAMA_HOST || 'http://localhost:11434';
        backend = await startBackend(host, 8080, ollamaBaseUrl, evidence);
        proxyHandle = await startProxy(host, 1420, backend.origin, evidence);
        proxy = proxyHandle.proxy;

        await runPlaywrightSmoke(proxyHandle.url, evidence);
      }
    } else {
      evidence.prechecks.push({
        name: 'base_url_reachable',
        url: baseUrlEnv,
        ok: await httpOk(`${baseUrlEnv}/`, 1500),
        at: nowIso(),
      });
      if (!evidence.prechecks[evidence.prechecks.length - 1].ok) {
        throw new Error(`BLOCKED: base URL not reachable (${baseUrlEnv}). Start the Desktop stack, or use boot mode on a machine that can bind ports.`);
      }
      await runPlaywrightSmoke(baseUrlEnv, evidence);
    }

    const console404 = (evidence.playwright && evidence.playwright.console && evidence.playwright.console.console_404) || [];
    const pageErrors = (evidence.playwright && evidence.playwright.page_errors) || [];
    const checks = (evidence.playwright && evidence.playwright.checks) || [];
    const doc404 = checks.filter((c) => c && c.iframe_doc && c.iframe_doc.status === 404);

    if (doc404.length > 0 || console404.length > 0 || pageErrors.length > 0) {
      evidence.status = 'FAIL';
      evidence.reason = `Detected errors: embedded_doc_404=${doc404.length} console_404=${console404.length} page_errors=${pageErrors.length}`;
    } else {
      evidence.status = 'PASS';
    }
  } catch (err) {
    const msg = String(err && err.stack ? err.stack : err);
    const blockedByDeps =
      msg.includes('Cannot find module') && (msg.includes('playwright') || msg.includes('@playwright/test'));
    const blockedByBrowsers =
      msg.toLowerCase().includes('executable doesn') ||
      msg.toLowerCase().includes('browser') && msg.toLowerCase().includes('install');
    evidence.status =
      msg.includes('BLOCKED:') ||
      blockedByDeps ||
      blockedByBrowsers ||
      msg.includes('webui dist not found') ||
      msg.includes('product dist not found')
        ? 'BLOCKED'
        : 'FAIL';
    evidence.reason = truncate(msg, 8000);
  } finally {
    evidence.ended_at = nowIso();
    try {
      fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n', 'utf8');
    } catch (e) {
      console.error('Failed to write evidence:', e);
    }

    try { if (proxy) await proxy.close(); } catch { /* ignore */ }

    // Stop backend process we started (if any).
    try { if (backend && backend.proc) backend.proc.kill(); } catch { /* ignore */ }
  }

  // Deterministic PASS/FAIL for CLI users. BLOCKED exits non-zero as well.
  if (evidence.status === 'PASS') {
    console.log('PASS', EVIDENCE_PATH);
    process.exit(0);
  } else {
    console.error(evidence.status, EVIDENCE_PATH);
    if (evidence.reason) console.error(truncate(evidence.reason, 1200));
    process.exit(1);
  }
}

void main();
