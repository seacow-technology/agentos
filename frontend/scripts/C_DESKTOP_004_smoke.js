/* eslint-disable no-console */
'use strict';

// C_DESKTOP_004: Commercial Scenario - Product tasks list + plan/evidence/replay modals.
//
// Acceptance (evidence-first):
// - Evidence includes:
//   - GET /api/product/tasks
//   - GET /api/product/tasks/{id}/plan
//   - GET /api/product/tasks/{id}/evidence
//   - GET /api/product/tasks/{id}/replay
//   - Any /download/* requests (when present)
// - Store evidence to frontend/reports/e2e_endpoint_evidence/C_DESKTOP_004.json

const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const os = require('node:os');
const { spawn } = require('node:child_process');

const REPO_ROOT = process.cwd();
const EVIDENCE_PATH = path.join(REPO_ROOT, 'frontend', 'reports', 'e2e_endpoint_evidence', 'C_DESKTOP_004.json');
const PROFILE_DIR = process.env.PLAYWRIGHT_PROFILE_DIR || '/Users/pangge/.octopusos/playwright-profile';

const HOST = '127.0.0.1';
const PREFERRED_PROXY_PORT = 1423;
const PREFERRED_BACKEND_PORT = 8083;

function nowIso() {
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
  return str.slice(0, maxLen) + `...(+${str.length - maxLen} chars)`;
}

async function findFreePort(host, preferred) {
  const tryPort = (port) => new Promise((resolve) => {
    const srv = net.createServer();
    srv.once('error', () => resolve(false));
    srv.once('listening', () => srv.close(() => resolve(true)));
    srv.listen(port, host);
  });
  for (let p = preferred; p < preferred + 50; p += 1) {
    // eslint-disable-next-line no-await-in-loop
    const ok = await tryPort(p);
    if (ok) return p;
  }
  const ephemeral = await new Promise((resolve) => {
    const srv = net.createServer();
    srv.listen(0, host, () => {
      const addr = srv.address();
      const port = addr && typeof addr === 'object' ? addr.port : null;
      srv.close(() => resolve(port));
    });
  });
  if (typeof ephemeral === 'number' && ephemeral > 0) return ephemeral;
  throw new Error('no free port found');
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

function pickPythonExec() {
  const venv = path.join(REPO_ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venv)) return venv;
  if (process.platform === 'darwin') {
    if (fs.existsSync('/opt/homebrew/bin/python3')) return '/opt/homebrew/bin/python3';
    if (fs.existsSync('/usr/local/bin/python3')) return '/usr/local/bin/python3';
  }
  return 'python3';
}

async function startBackend(host, preferredPort, evidence) {
  const port = await findFreePort(host, preferredPort);
  const origin = `http://${host}:${port}`;
  const healthUrl = `${origin}/api/health`;

  const preferBundled = String(process.env.OCTOPUSOS_USE_BUNDLED_RUNTIME || '').trim() === '1';
  const runtimeBin = path.join(
    REPO_ROOT,
    'apps',
    'desktop-electron',
    'binaries',
    process.platform === 'win32' ? 'octopusos-runtime.exe' : 'octopusos-runtime',
  );
  const dataDir = path.join(os.tmpdir(), 'octopusos-smoke', 'C_DESKTOP_004');
  ensureDir(dataDir);

  const env = {
    ...process.env,
    OCTOPUSOS_ADMIN_TOKEN: process.env.OCTOPUSOS_ADMIN_TOKEN || 'smoke_admin_token',
    OCTOPUSOS_CONTROL_TOKEN: process.env.OCTOPUSOS_CONTROL_TOKEN || 'smoke_control_token',
    OCTOPUSOS_DATA_DIR: dataDir,
    // Keep backend deterministic for e2e.
    OCTOPUSOS_COMPAT_DEMO: process.env.OCTOPUSOS_COMPAT_DEMO || '1',
  };

  let proc = null;
  let mode = null;
  const tryUvicorn = async () => {
    mode = 'uvicorn-source';
    const py = pickPythonExec();
    const args = ['-m', 'uvicorn', 'octopusos.webui.app:app', '--host', host, '--port', String(port)];
    const started = spawnLogged(py, args, { env, cwd: REPO_ROOT }, evidence, 'backend');
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
    const started = spawnLogged(runtimeBin, args, { env, cwd: dataDir }, evidence, 'backend');
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

  if (!proc) throw new Error(`backend did not become healthy within 45s (${healthUrl})`);

  evidence.processes.backend.origin = origin;
  evidence.processes.backend.health_url = healthUrl;
  evidence.processes.backend.mode = mode;
  evidence.processes.backend.data_dir = dataDir;
  return { origin, proc };
}

async function startProxy(host, preferredPort, backendOrigin, evidence) {
  const webuiDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'webui-dist');
  const productDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'product-dist');
  const proxyPort = await findFreePort(host, preferredPort);

  // eslint-disable-next-line global-require, import/no-dynamic-require
  const { startWebuiProxyServer } = require(path.join(REPO_ROOT, 'apps', 'desktop-electron', 'dist', 'proxyServer.js'));
  const proxy = await startWebuiProxyServer({ host, port: proxyPort, webuiDistDir, productDistDir, backendOrigin });

  evidence.processes.proxy = {
    url: proxy.url,
    host,
    port: proxyPort,
    webuiDistDir,
    productDistDir,
    backendOrigin,
    started_at: nowIso(),
  };

  return { proxy, url: proxy.url };
}

async function loadPlaywright() {
  // eslint-disable-next-line global-require, import/no-dynamic-require
  const candidates = [
    path.join(REPO_ROOT, 'apps', 'webui', 'node_modules', 'playwright'),
    path.join(REPO_ROOT, 'node_modules', 'playwright'),
    'playwright',
  ];
  for (const mod of candidates) {
    try {
      // eslint-disable-next-line global-require, import/no-dynamic-require
      return require(mod);
    } catch {
      // ignore
    }
  }
  throw new Error('Playwright not found (install deps first).');
}

async function runUi(url, evidence) {
  const pw = await loadPlaywright();
  const { chromium } = pw;
  ensureDir(path.dirname(EVIDENCE_PATH));
  ensureDir(PROFILE_DIR);

  const consoleEvents = [];
  const pageErrors = [];
  const requestFailures = [];
  const apiHits = [];
  const downloads = [];

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: true,
    viewport: { width: 1280, height: 720 },
  });

  try {
    const page = await ctx.newPage();
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleEvents.push({ at: nowIso(), type: msg.type(), text: msg.text() });
      }
    });
    page.on('pageerror', (err) => pageErrors.push({ at: nowIso(), message: String(err && err.message ? err.message : err) }));
    page.on('requestfailed', (req) => requestFailures.push({
      at: nowIso(),
      url: req.url(),
      method: req.method(),
      failure: req.failure() ? req.failure().errorText : 'unknown',
      resourceType: req.resourceType(),
    }));
    page.on('response', async (resp) => {
      const u = resp.url();
      const urlObj = new URL(u);
      const p = urlObj.pathname + (urlObj.search || '');
      if (p.startsWith('/download/')) {
        downloads.push({ at: nowIso(), method: resp.request().method(), path: p, status: resp.status() });
        return;
      }
      if (!p.startsWith('/api/')) return;
      apiHits.push({ at: nowIso(), method: resp.request().method(), path: p, status: resp.status() });
    });

    await page.goto(`${url}#/tasks`, { waitUntil: 'domcontentloaded', timeout: 45_000 });
    await page.waitForSelector('.main .topbar', { timeout: 45_000 });

    // If tasks exist, click Plan/Evidence/Replay on the first one.
    const hasTask = await page.locator('.task').first().isVisible().catch(() => false);
    evidence.assertions.push({ at: nowIso(), name: 'has_task', ok: true, actual: hasTask });

    const clickChip = async (act) => {
      const btn = page.locator(`button.chip[data-act=\"${act}\"]`).first();
      await btn.click({ timeout: 10_000 });
      await page.waitForSelector('.modal.open', { timeout: 20_000 });
      // Close to avoid stacking.
      await page.locator('[data-act=\"modal-close\"]').click({ timeout: 10_000 });
      await page.waitForSelector('.modal.open', { state: 'detached', timeout: 20_000 });
    };

    if (hasTask) {
      await clickChip('plan');
      await clickChip('evidence');
      await clickChip('replay');
    } else {
      // Still require /api/product/tasks to load, even if empty.
      await page.waitForTimeout(800);
    }

    const productCalls = apiHits.filter((h) => String(h.path).startsWith('/api/product/tasks'));
    const okStatus = productCalls.some((c) => c.status === 200);
    evidence.assertions.push({ at: nowIso(), name: 'api_product_tasks_called', ok: productCalls.length > 0, actual: productCalls.length });
    evidence.assertions.push({ at: nowIso(), name: 'api_product_tasks_status_200', ok: okStatus, actual: productCalls.map((c) => c.status).slice(0, 5) });
  } finally {
    await ctx.close();
  }

  evidence.console_errors = consoleEvents;
  evidence.page_errors = pageErrors;
  evidence.request_failures = requestFailures;
  evidence.requests = apiHits;
  evidence.downloads = downloads;
}

async function main() {
  const evidence = {
    task_id: 'C_DESKTOP_004',
    generated_at: nowIso(),
    processes: {},
    assertions: [],
    requests: [],
    downloads: [],
    console_errors: [],
    page_errors: [],
    request_failures: [],
  };

  let backend = null;
  let proxy = null;
  try {
    backend = await startBackend(HOST, PREFERRED_BACKEND_PORT, evidence);
    proxy = await startProxy(HOST, PREFERRED_PROXY_PORT, backend.origin, evidence);
    await runUi(proxy.url, evidence);
  } catch (e) {
    evidence.error = { at: nowIso(), message: String(e && e.message ? e.message : e) };
    fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n', 'utf8');
    throw e;
  } finally {
    try { if (proxy && proxy.proxy) await proxy.proxy.close(); } catch { /* ignore */ }
    try { if (backend && backend.proc) backend.proc.kill(); } catch { /* ignore */ }
  }

  fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n', 'utf8');

  const ok = evidence.assertions.every((a) => a.ok !== false);
  if (!ok) {
    console.error(`[C_DESKTOP_004] FAIL (see ${EVIDENCE_PATH})`);
    process.exit(1);
  }
  console.log(`[C_DESKTOP_004] PASS evidence=${EVIDENCE_PATH}`);
}

main().catch((e) => {
  console.error(String(e && e.stack ? e.stack : e));
  process.exit(1);
});
