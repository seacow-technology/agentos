/* eslint-disable no-console */
'use strict';

// C_DESKTOP_001: Commercial Scenario - Product Shell tab navigation via embedded Console.
//
// Hard constraints:
// - Do not invent endpoints: this script uses only repo-evidenced paths:
//   - Product Shell routes live in apps/desktop-electron/resources/product-dist/app.js (#/chat etc)
//   - Embedded Console is mounted at /console/* with ?embed=1 (apps/desktop-electron/src/proxyServer.ts)
//   - Backend health is reachable at GET /api/health (apps/desktop-electron/src/main.ts)
// - Smoke is against an already-running Desktop stack (Electron proxy + backend).
// - Evidence must be written to frontend/reports/e2e_endpoint_evidence/C_DESKTOP_001.json

const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const os = require('node:os');
const { spawn } = require('node:child_process');
const { createRequire } = require('node:module');

const REPO_ROOT = process.cwd();
const EVIDENCE_PATH = path.join(REPO_ROOT, 'frontend', 'reports', 'e2e_endpoint_evidence', 'C_DESKTOP_001.json');
const RAW_DIR = path.join(REPO_ROOT, 'frontend', 'reports', 'e2e_endpoint_evidence', '_raw');

const PROFILE_DIR = process.env.PLAYWRIGHT_PROFILE_DIR || '/Users/pangge/.octopusos/playwright-profile';
const HOST = '127.0.0.1';
const PREFERRED_FRONTEND_PORT = 1420; // apps/desktop-electron/src/main.ts
const PREFERRED_BACKEND_PORT = 8080; // apps/desktop-electron/src/main.ts
// Default to booting a deterministic local stack for CI/driver usage.
const MODE = (process.env.C_DESKTOP_001_MODE || 'boot').trim(); // running|boot

function nowIso() {
  // Truncate ms for stability in diffs.
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
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

async function fetchWithTimeout(url, opts = {}) {
  const timeoutMs = typeof opts.timeoutMs === 'number' ? opts.timeoutMs : 1200;
  const method = opts.method || 'GET';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    // eslint-disable-next-line no-undef
    const resp = await fetch(url, { method, signal: controller.signal });
    const text = await resp.text().catch(() => '');
    return { ok: resp.ok, status: resp.status, text, headers: Object.fromEntries(resp.headers.entries()), error: null };
  } catch (e) {
    const cause = e && e.cause ? e.cause : null;
    const err = {
      name: e && e.name ? String(e.name) : 'Error',
      message: e && e.message ? String(e.message) : String(e),
      code: cause && cause.code ? String(cause.code) : (e && e.code ? String(e.code) : null),
      syscall: cause && cause.syscall ? String(cause.syscall) : (e && e.syscall ? String(e.syscall) : null),
      address: cause && cause.address ? String(cause.address) : (e && e.address ? String(e.address) : null),
      port: cause && typeof cause.port === 'number' ? cause.port : (e && typeof e.port === 'number' ? e.port : null),
    };
    return { ok: false, status: null, text: err.message, headers: {}, error: err };
  } finally {
    clearTimeout(timer);
  }
}

function isFavicon(url) {
  try {
    const u = new URL(url);
    return u.pathname.endsWith('/favicon.ico');
  } catch {
    return false;
  }
}

async function canBindLocalPorts(host) {
  // Some environments disallow listen() entirely. Boot mode requires binding ports.
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

async function startBackend(host, preferredPort, evidence) {
  const port = await findFreePort(host, preferredPort);
  const origin = `http://${host}:${port}`;
  const healthUrl = `${origin}/api/health`;

  const runtimeBin = path.join(
    REPO_ROOT,
    'apps',
    'desktop-electron',
    'binaries',
    process.platform === 'win32' ? 'octopusos-runtime.exe' : 'octopusos-runtime',
  );
  const dataDir = path.join(os.tmpdir(), 'octopusos-smoke', 'C_DESKTOP_001');
  ensureDir(dataDir);

  const commonEnv = {
    ...process.env,
    OCTOPUSOS_ADMIN_TOKEN: process.env.OCTOPUSOS_ADMIN_TOKEN || 'smoke_admin_token',
    OCTOPUSOS_CONTROL_TOKEN: process.env.OCTOPUSOS_CONTROL_TOKEN || 'smoke_control_token',
    OCTOPUSOS_DATA_DIR: dataDir,
    OCTOPUSOS_COMPAT_DEMO: process.env.OCTOPUSOS_COMPAT_DEMO || '1',
  };

  const preferBundled = String(process.env.OCTOPUSOS_USE_BUNDLED_RUNTIME || '').trim() === '1';
  let proc = null;
  let mode = null;

  const pickPythonExec = () => {
    const venvPython = path.join(REPO_ROOT, '.venv', 'bin', 'python');
    if (fs.existsSync(venvPython)) return venvPython;
    if (process.platform === 'darwin') {
      if (fs.existsSync('/opt/homebrew/bin/python3')) return '/opt/homebrew/bin/python3';
      if (fs.existsSync('/usr/local/bin/python3')) return '/usr/local/bin/python3';
    }
    return 'python3';
  };

  const tryUvicorn = async () => {
    mode = 'uvicorn-source';
    const py = pickPythonExec();
    const args = ['-m', 'uvicorn', 'octopusos.webui.app:app', '--host', host, '--port', String(port)];
    const started = spawnLogged(py, args, { env: commonEnv, cwd: REPO_ROOT }, evidence, 'backend');
    proc = started.child;
    const ok = await httpOk(healthUrl, 45_000);
    if (!ok) {
      started.refreshTails();
      try { proc.kill(); } catch { /* ignore */ }
      proc = null;
      mode = null;
    }
  };

  const tryBundled = async () => {
    if (!fs.existsSync(runtimeBin)) return;
    mode = 'bundled-runtime';
    const args = ['webui', 'start', '--backend-only', '--foreground', '--host', host, '--port', String(port)];
    const started = spawnLogged(runtimeBin, args, { env: commonEnv, cwd: dataDir }, evidence, 'backend');
    proc = started.child;
    const ok = await httpOk(healthUrl, 45_000);
    if (!ok) {
      started.refreshTails();
      try { proc.kill(); } catch { /* ignore */ }
      proc = null;
      mode = null;
    }
  };

  if (preferBundled) {
    await tryBundled();
    if (!proc) await tryUvicorn();
  } else {
    await tryUvicorn();
    if (!proc) await tryBundled();
  }

  if (!proc) throw new Error(`Backend did not become healthy within 45s (${healthUrl}). See evidence logs.`);

  evidence.processes.backend.origin = origin;
  evidence.processes.backend.health_url = healthUrl;
  evidence.processes.backend.mode = mode;
  evidence.processes.backend.data_dir = dataDir;
  return { origin, port, proc, healthUrl, dataDir };
}

async function startProxy(host, preferredPort, backendOrigin, evidence) {
  const webuiDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'webui-dist');
  const productDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'product-dist');

  const webuiIndex = path.join(webuiDistDir, 'index.html');
  const productIndex = path.join(productDistDir, 'index.html');
  if (!fs.existsSync(webuiIndex)) throw new Error(`webui dist not found: missing ${webuiIndex}`);
  if (!fs.existsSync(productIndex)) throw new Error(`product dist not found: missing ${productIndex}`);

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

async function detectDesktopOrigin(evidence) {
  if (process.env.OCTOPUSOS_DESKTOP_ORIGIN) {
    const origin = process.env.OCTOPUSOS_DESKTOP_ORIGIN.replace(/\/+$/, '');
    evidence.origin_detection = { mode: 'env', origin };
    return origin;
  }

  // Electron selects the first available port starting at PREFERRED_FRONTEND_PORT.
  // We can't bind/scan ports by listening in this environment, but we can probe with HTTP.
  const candidates = [];
  // Source of truth: apps/desktop-electron/src/util/ports.ts uses searchRange=200 by default.
  for (let p = PREFERRED_FRONTEND_PORT; p < PREFERRED_FRONTEND_PORT + 201; p++) candidates.push(p);

  const probeSamples = [];

  for (const port of candidates) {
    // eslint-disable-next-line no-await-in-loop
    const health = await fetchWithTimeout(`http://${HOST}:${port}/api/health`, { timeoutMs: 900 });
    if (!health.ok && health.error && health.error.code === 'EPERM' && health.error.syscall === 'connect') {
      evidence.origin_detection = {
        mode: 'connect_eperm',
        host: HOST,
        port,
        error: health.error,
        notes:
          'This environment forbids TCP connect() to localhost (EPERM). ' +
          'Playwright cannot reach the running Desktop proxy here; run this smoke on a host environment that allows localhost networking, ' +
          'or set OCTOPUSOS_DESKTOP_ORIGIN to an accessible origin.',
      };
      return null;
    }
    if (!health.ok) continue;

    // eslint-disable-next-line no-await-in-loop
    const appJs = await fetchWithTimeout(`http://${HOST}:${port}/app.js`, { timeoutMs: 900 });
    const looksLikeProduct = appJs.ok && /Product Shell/.test(appJs.text || '');
    if (!looksLikeProduct) continue;

    // eslint-disable-next-line no-await-in-loop
    const consoleIndex = await fetchWithTimeout(`http://${HOST}:${port}/console/`, { timeoutMs: 900 });
    if (!consoleIndex.ok) continue;

    const origin = `http://${HOST}:${port}`;
    evidence.origin_detection = {
      mode: 'probe',
      origin,
      probes: {
        health: { status: health.status },
        app_js: { status: appJs.status, snippet: truncate(appJs.text, 200) },
        console: { status: consoleIndex.status },
      },
    };
    return origin;
  }

  // Keep a small sample of probe failures for evidence without bloating JSON.
  // Try the preferred port only; if it fails, the rest likely fail similarly.
  // eslint-disable-next-line no-await-in-loop
  const pref = await fetchWithTimeout(`http://${HOST}:${PREFERRED_FRONTEND_PORT}/api/health`, { timeoutMs: 900 });
  probeSamples.push({
    port: PREFERRED_FRONTEND_PORT,
    url: `http://${HOST}:${PREFERRED_FRONTEND_PORT}/api/health`,
    status: pref.status,
    error: pref.error,
    body_snippet: truncate(pref.text, 120),
  });

  evidence.origin_detection = {
    mode: 'probe_failed',
    tried_ports: candidates,
    probe_samples: probeSamples,
    notes: 'No running Desktop proxy detected. Ensure Desktop stack is running (Electron proxy serves Product at / and Console at /console/).',
  };

  // Extra context (still repo-evidenced): backend health usually on port ~8080.
  // This does not "invent" product routes; it only helps distinguish "backend-only running" vs "nothing running".
  const backendCandidates = [];
  for (let p = PREFERRED_BACKEND_PORT; p < PREFERRED_BACKEND_PORT + 201; p++) backendCandidates.push(p);
  for (const port of backendCandidates) {
    // eslint-disable-next-line no-await-in-loop
    const health = await fetchWithTimeout(`http://${HOST}:${port}/api/health`, { timeoutMs: 900 });
    if (!health.ok) continue;
    evidence.origin_detection.backend_only = {
      detected: true,
      origin: `http://${HOST}:${port}`,
      health_status: health.status,
      notes: 'Backend responds to /api/health, but Electron proxy (Product at / and Console at /console/) was not detected on the expected frontend port range.',
    };
    break;
  }
  return null;
}

function buildTabs() {
  // Source of truth: apps/desktop-electron/resources/product-dist/app.js render() mapping.
  return [
    { name: 'Chat', product_hash: '#/chat', console_path: '/chat' },
    { name: 'Work', product_hash: '#/work', console_path: '/chat/work' },
    { name: 'Coding', product_hash: '#/coding', console_path: '/coding' },
    { name: 'Projects', product_hash: '#/projects', console_path: '/projects' },
    { name: 'AWS Ops', product_hash: '#/aws', console_path: '/aws' },
    { name: 'Tasks', product_hash: '#/tasks', console_path: null },
  ];
}

async function main() {
  ensureDir(path.dirname(EVIDENCE_PATH));
  ensureDir(RAW_DIR);

  const evidence = {
    task_id: 'C_DESKTOP_001',
    portal: 'desktop',
    bucket: 'commercial/product_shell_navigation',
    run_at: nowIso(),
    status: 'in_progress',
    env: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
      cwd: REPO_ROOT,
    },
    origin_detection: null,
    origin: null,
    prechecks: [],
    processes: {},
    intended_tabs: buildTabs().map((t) => ({
      name: t.name,
      product_route: t.product_hash,
      iframe_src: t.console_path ? `/console${t.console_path}?embed=1` : null,
    })),
    run: {
      playwright: null,
      totals: { console_errors: 0, page_errors: 0, bad_http_responses: 0, embed_chrome_failures: 0 },
      root: null,
      tabs: [],
      notes: [],
    },
  };

  let backend = null;
  let proxyHandle = null;

  try {
    if (MODE !== 'running' && MODE !== 'boot') {
      throw new Error(`Invalid C_DESKTOP_001_MODE=${MODE} (expected running|boot)`);
    }

    let origin = null;
    if (MODE === 'running') {
      origin = await detectDesktopOrigin(evidence);
      evidence.origin = origin;
      if (!origin) {
        evidence.status = 'BLOCKED';
        evidence.run.notes.push('BLOCKED: Desktop proxy origin could not be detected.');
        return;
      }
    } else {
      const bind = await canBindLocalPorts(HOST);
      evidence.prechecks.push({
        name: 'can_bind_ports',
        host: HOST,
        ok: !!(bind && bind.ok),
        error: bind && bind.err ? { code: bind.err.code, message: String(bind.err.message || bind.err) } : null,
        at: nowIso(),
      });
      if (!bind.ok) {
        // Some sandboxes disallow listen() entirely. In that case, we cannot "boot" a stack here.
        // Still try to detect an already-running Desktop proxy so the evidence file carries useful context.
        evidence.run.notes.push(`BLOCKED: cannot bind ports required for boot mode (host=${HOST}).`);
        const runningOrigin = await detectDesktopOrigin(evidence);
        evidence.origin = runningOrigin;
        evidence.origin_detection = evidence.origin_detection || { mode: 'boot_bind_failed' };
        evidence.status = 'BLOCKED';
        return;
      }
      backend = await startBackend(HOST, PREFERRED_BACKEND_PORT, evidence);
      proxyHandle = await startProxy(HOST, PREFERRED_FRONTEND_PORT, backend.origin, evidence);
      origin = proxyHandle.url;
      evidence.origin_detection = { mode: 'boot', origin };
      evidence.origin = origin;
    }

    const originNoSlash = origin.replace(/\/+$/, '');
    evidence.origin = originNoSlash;

    evidence.origin = origin;

    // Prechecks (repo-evidenced endpoints only)
    {
      const urls = [`${originNoSlash}/api/health`, `${originNoSlash}/`, `${originNoSlash}/console/`];
      for (const url of urls) {
        // eslint-disable-next-line no-await-in-loop
        const r = await fetchWithTimeout(url, { timeoutMs: 1500 });
        evidence.prechecks.push({
          url,
          observed_status: r.status,
          ok: !!r.ok,
          body_snippet: truncate(r.text, 240),
        });
      }
    }

    const requireFromWebui = createRequire(path.join(REPO_ROOT, 'apps', 'webui', 'package.json'));
    const { chromium } = requireFromWebui('playwright');

    const headless = process.env.HEADLESS === '0' ? false : true;
    ensureDir(PROFILE_DIR);

    let context = null;
    try {
      context = await chromium.launchPersistentContext(PROFILE_DIR, {
        channel: 'chrome',
        headless,
        viewport: { width: 1400, height: 900 },
      });
      evidence.run.playwright = { engine: 'chromium', channel: 'chrome', headless, profile_dir: PROFILE_DIR };
    } catch (e) {
      // Fallback: bundled Chromium if Chrome channel is not available.
      context = await chromium.launchPersistentContext(PROFILE_DIR, {
        headless,
        viewport: { width: 1400, height: 900 },
      });
      evidence.run.playwright = {
        engine: 'chromium',
        channel: null,
        headless,
        profile_dir: PROFILE_DIR,
        fallback_reason: String(e && e.message ? e.message : e),
      };
    }

    const page = await context.newPage();

    const events = {
      console: [],
      pageerror: [],
      responses: [],
      requestsFailed: [],
    };

    const recordConsole = (msg) => {
      events.console.push({
        at: Date.now(),
        type: msg.type(),
        text: truncate(msg.text(), 2000),
        location: msg.location ? msg.location() : undefined,
      });
    };
    const recordPageError = (err) => {
      events.pageerror.push({
        at: Date.now(),
        message: truncate(String(err && err.message ? err.message : err), 4000),
        stack: truncate(String(err && err.stack ? err.stack : ''), 8000),
      });
    };
    const recordResponse = async (resp) => {
      try {
        const url = resp.url();
        const status = resp.status();
        const ok = resp.ok();
        const req = resp.request();
        events.responses.push({
          at: Date.now(),
          url,
          method: req.method(),
          resourceType: req.resourceType(),
          status,
          ok,
        });
      } catch {
        // ignore
      }
    };
    const recordRequestFailed = (req) => {
      events.requestsFailed.push({
        at: Date.now(),
        url: req.url(),
        method: req.method(),
        resourceType: req.resourceType(),
        failure: req.failure() ? truncate(req.failure().errorText, 2000) : 'unknown',
      });
    };

    page.on('console', recordConsole);
    page.on('pageerror', recordPageError);
    page.on('response', recordResponse);
    page.on('requestfailed', recordRequestFailed);

    // Load Product Shell
    await page.goto(`${originNoSlash}/`, { waitUntil: 'domcontentloaded', timeout: 45_000 });
    await page.waitForTimeout(1500);

    // Root asset sanity (ensures broken assets/errors on initial load aren't ignored).
    {
      const badResponses = events.responses.filter((r) => r && typeof r.status === 'number' && r.status >= 400 && !isFavicon(r.url));
      const consoleErrors = events.console.filter((m) => m && m.type === 'error');
      evidence.run.totals.console_errors += consoleErrors.length;
      evidence.run.totals.page_errors += events.pageerror.length;
      evidence.run.totals.bad_http_responses += badResponses.length + events.requestsFailed.length;
      evidence.run.root = {
        bad_http_responses: badResponses,
        request_failed: events.requestsFailed,
        console_errors: consoleErrors,
        page_errors: events.pageerror,
      };
      // Reset counters so per-tab slices remain clean.
      events.console = [];
      events.pageerror = [];
      events.responses = [];
      events.requestsFailed = [];
    }

    const tabs = buildTabs();
    for (const tab of tabs) {
      const marks = {
        console: events.console.length,
        pageerror: events.pageerror.length,
        responses: events.responses.length,
        requestfailed: events.requestsFailed.length,
      };

      // Click left nav by link text; also safe to set hash directly.
      const navLocator = page.locator(`a[href="${tab.product_hash}"]`);
      if (await navLocator.count()) await navLocator.first().click({ timeout: 10_000 });
      else await page.evaluate((h) => { location.hash = h; }, tab.product_hash);

      // Wait route reflected.
      await page.waitForFunction(
        (expected) => location.hash === expected,
        tab.product_hash,
        { timeout: 10_000 },
      );

      // If embedded, wait for iframe src + for embed mode to strip chrome.
      let iframeUrl = null;
      let embedChrome = null;
      let embedChecks = null;
      if (tab.console_path) {
        const expectedSrc = `/console${tab.console_path}?embed=1`;
        const iframe = page.locator('iframe.embedFrame');
        await iframe.waitFor({ state: 'attached', timeout: 15_000 });
        await page.waitForFunction((src) => {
          const el = document.querySelector('iframe.embedFrame');
          return el && el.getAttribute('src') === src;
        }, expectedSrc, { timeout: 15_000 });

        // Let iframe settle.
        await page.waitForTimeout(1200);

        const frame = await (async () => {
          const h = await iframe.elementHandle();
          if (!h) return null;
          return h.contentFrame();
        })();

        if (frame) {
          iframeUrl = frame.url();
          // "No duplicate nav chrome": embedded mode should omit MUI Drawer/AppBar.
          embedChecks = await frame.evaluate(() => {
            const hasDrawer = !!document.querySelector('.MuiDrawer-root, [class*=\"MuiDrawer-\"]');
            const hasAppBar = !!document.querySelector('.MuiAppBar-root, [class*=\"MuiAppBar-\"]');
            return { hasDrawer, hasAppBar };
          }).catch(() => null);
          embedChrome = embedChecks ? (!embedChecks.hasDrawer && !embedChecks.hasAppBar) : null;
        }
      } else {
        // Non-embedded tab: allow any final paint.
        await page.waitForTimeout(800);
      }

      // Small idle window to collect late requests.
      await page.waitForTimeout(1500);

      const consoleSlice = events.console.slice(marks.console);
      const pageErrorSlice = events.pageerror.slice(marks.pageerror);
      const responsesSlice = events.responses.slice(marks.responses);
      const failedSlice = events.requestsFailed.slice(marks.requestfailed);

      const badResponses = responsesSlice.filter((r) => r && typeof r.status === 'number' && r.status >= 400 && !isFavicon(r.url));
      const consoleErrors = consoleSlice.filter((m) => m && m.type === 'error');
      const embedChromeOk = tab.console_path ? embedChrome === true : null;
      const embedChromeFailure = tab.console_path ? embedChromeOk !== true : false;

      evidence.run.totals.console_errors += consoleErrors.length;
      evidence.run.totals.page_errors += pageErrorSlice.length;
      evidence.run.totals.bad_http_responses += badResponses.length + failedSlice.length;
      evidence.run.totals.embed_chrome_failures += embedChromeFailure ? 1 : 0;

      evidence.run.tabs.push({
        name: tab.name,
        product_hash: tab.product_hash,
        expected_iframe_src: tab.console_path ? `/console${tab.console_path}?embed=1` : null,
        observed_iframe_url: iframeUrl,
        embed_chrome_ok: embedChromeOk,
        embed_chrome_checks: embedChecks,
        console_errors: consoleErrors,
        page_errors: pageErrorSlice,
        bad_http_responses: badResponses,
        request_failed: failedSlice,
      });
    }

    const hasAnyConsoleError = evidence.run.totals.console_errors > 0;
    const hasAnyPageError = evidence.run.totals.page_errors > 0;
    const hasAnyBadHttp = evidence.run.totals.bad_http_responses > 0;
    const hasAnyEmbedChromeFailure = evidence.run.totals.embed_chrome_failures > 0;

    if (!hasAnyConsoleError && !hasAnyPageError && !hasAnyBadHttp && !hasAnyEmbedChromeFailure) evidence.status = 'PASS';
    else evidence.status = 'FAIL';

    // Save raw event log for debugging without bloating the main JSON.
    const rawPath = path.join(RAW_DIR, `C_DESKTOP_001_events_${Date.now()}.json`);
    fs.writeFileSync(rawPath, JSON.stringify(events, null, 2));
    evidence.run.raw_events_path = path.relative(REPO_ROOT, rawPath);

    await context.close();
  } catch (err) {
    evidence.status = 'BLOCKED';
    evidence.run.notes.push(`BLOCKED: exception during run: ${String(err && err.stack ? err.stack : err)}`);
  } finally {
    try { if (proxyHandle && proxyHandle.proxy) await proxyHandle.proxy.close(); } catch { /* ignore */ }
    try { if (backend && backend.proc) backend.proc.kill(); } catch { /* ignore */ }
    fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2));
  }

  return evidence.status === 'PASS' ? 0 : 1;
}

if (require.main === module) {
  // eslint-disable-next-line promise/catch-or-return
  main().then((rc) => process.exit(rc)).catch(() => process.exit(1));
}
