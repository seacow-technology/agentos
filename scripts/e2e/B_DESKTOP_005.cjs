/* eslint-disable no-console */
// B_DESKTOP_005: Playwright smoke for Desktop Product Shell + embedded Console routes.
//
// Single-command deterministic PASS/FAIL (or BLOCKED) runner.
// Evidence is always written to:
//   frontend/reports/e2e_endpoint_evidence/B_DESKTOP_005.json
//
// Hard constraints:
// - Do not invent endpoints: route list comes from apps/desktop-electron/resources/product-dist/app.js
// - Do not touch publish/webui-v2/

const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const net = require('node:net');
const { spawn } = require('node:child_process');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const EVIDENCE_PATH = path.join(
  REPO_ROOT,
  'frontend',
  'reports',
  'e2e_endpoint_evidence',
  'B_DESKTOP_005.json',
);

function isoNow() {
  return new Date().toISOString();
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function ensureDir(p) {
  await fs.promises.mkdir(p, { recursive: true });
}

async function getFreePort(host) {
  return await new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, host, () => {
      const addr = srv.address();
      const port = addr && typeof addr === 'object' ? addr.port : null;
      srv.close(() => resolve(port));
    });
  });
}

async function httpGetJson(url, timeoutMs) {
  return await new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = http.request(
      {
        method: 'GET',
        hostname: u.hostname,
        port: u.port,
        path: u.pathname + u.search,
        protocol: u.protocol,
        timeout: timeoutMs,
      },
      (res) => {
        const chunks = [];
        res.on('data', (d) => chunks.push(d));
        res.on('end', () => {
          const raw = Buffer.concat(chunks).toString('utf8');
          let parsed = null;
          try {
            parsed = JSON.parse(raw);
          } catch {
            // ignore
          }
          resolve({ status: res.statusCode || 0, raw, json: parsed });
        });
      },
    );
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', reject);
    req.end();
  });
}

async function waitForHealth(backendOrigin, timeoutMs) {
  const started = Date.now();
  const url = `${backendOrigin}/api/health`;
  while (Date.now() - started < timeoutMs) {
    try {
      const r = await httpGetJson(url, 800);
      if (r.status >= 200 && r.status < 300) return { ok: true, health: r.json || null };
    } catch {
      // ignore
    }
    await sleep(250);
  }
  return { ok: false, health: null };
}

function safeUnlink(p) {
  try {
    fs.unlinkSync(p);
  } catch {
    // ignore
  }
}

async function writeEvidence(evidence) {
  await ensureDir(path.dirname(EVIDENCE_PATH));
  const tmp = `${EVIDENCE_PATH}.tmp`;
  await fs.promises.writeFile(tmp, JSON.stringify(evidence, null, 2) + '\n', 'utf8');
  // Atomic-ish replace for readers.
  safeUnlink(EVIDENCE_PATH);
  await fs.promises.rename(tmp, EVIDENCE_PATH);
}

function getDesktopProxyModule() {
  const modPath = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'dist', 'proxyServer.js');
  if (!fs.existsSync(modPath)) throw new Error(`missing proxy module: ${modPath}`);
  // eslint-disable-next-line import/no-dynamic-require, global-require
  return require(modPath);
}

function getPlaywrightChromium() {
  const pwPath = path.join(REPO_ROOT, 'apps', 'webui', 'node_modules', 'playwright');
  if (!fs.existsSync(pwPath)) throw new Error(`missing playwright dependency: ${pwPath}`);
  // eslint-disable-next-line import/no-dynamic-require, global-require
  const pw = require(pwPath);
  if (!pw || !pw.chromium) throw new Error('playwright.chromium not found');
  return pw.chromium;
}

function getProductShellTabsFromRepoEvidence() {
  // Repo evidence: apps/desktop-electron/resources/product-dist/app.js render() mapping:
  //   /chat -> /console/chat?embed=1
  //   /work -> /console/chat/work?embed=1
  //   /coding -> /console/coding?embed=1
  //   /projects -> /console/projects?embed=1
  //   /aws -> /console/aws?embed=1
  //
  // Keep this list in sync with that file; do not invent new routes.
  return [
    { label: 'Chat', hashRoute: '/chat', consolePath: '/chat' },
    { label: 'Work', hashRoute: '/work', consolePath: '/chat/work' },
    { label: 'Coding', hashRoute: '/coding', consolePath: '/coding' },
    { label: 'Projects', hashRoute: '/projects', consolePath: '/projects' },
    { label: 'AWS Ops', hashRoute: '/aws', consolePath: '/aws' },
  ];
}

function isIgnorable404(url) {
  try {
    const u = new URL(url);
    const p = u.pathname || '';
    if (p === '/favicon.ico') return true;
    return false;
  } catch {
    return false;
  }
}

async function main() {
  const evidence = {
    task_id: 'B_DESKTOP_005',
    started_at: isoNow(),
    ended_at: null,
    status: 'BLOCKED',
    reason: null,
    backend: null,
    proxy: null,
    run: {
      node: process.version,
      cwd: process.cwd(),
      repo_root: REPO_ROOT,
      mode: null,
    },
    tabs: [],
    console: {
      errors: [],
      pageerrors: [],
    },
    network: {
      requestfailed: [],
      responses_4xx_5xx: [],
    },
    summary: null,
  };

  let backendProc = null;
  let proxyServer = null;
  let pwContext = null;

  const cleanup = async () => {
    try {
      if (pwContext) await pwContext.close();
    } catch {
      // ignore
    }
    pwContext = null;
    try {
      if (proxyServer) await proxyServer.close();
    } catch {
      // ignore
    }
    proxyServer = null;
    try {
      if (backendProc && backendProc.pid) backendProc.kill('SIGTERM');
    } catch {
      // ignore
    }
    backendProc = null;
  };

  const finalize = async (status, reason) => {
    evidence.ended_at = isoNow();
    evidence.status = status;
    evidence.reason = reason || null;
    evidence.summary = {
      tabs_total: evidence.tabs.length,
      console_errors_total: evidence.console.errors.length,
      console_404_errors_total: evidence.console.errors.filter((e) => e.is_404).length,
      pageerrors_total: evidence.console.pageerrors.length,
      requestfailed_total: evidence.network.requestfailed.length,
      responses_4xx_5xx_total: evidence.network.responses_4xx_5xx.length,
    };
    await writeEvidence(evidence);
  };

  process.on('SIGINT', () => {
    // Best-effort evidence write on Ctrl+C.
    // eslint-disable-next-line no-void
    void (async () => {
      await cleanup();
      await finalize('FAIL', 'Interrupted (SIGINT)');
      process.exit(1);
    })();
  });
  process.on('SIGTERM', () => {
    // eslint-disable-next-line no-void
    void (async () => {
      await cleanup();
      await finalize('FAIL', 'Interrupted (SIGTERM)');
      process.exit(1);
    })();
  });

  try {
    // Optional "connect-only" mode for environments where binding sockets is not permitted
    // (for example, restricted sandboxes). If provided, we do not start backend/proxy;
    // we only run the Playwright assertions against the already-running Desktop stack.
    const connectOnlyFrontend = String(process.env.B_DESKTOP_005_FRONTEND_URL || '').trim();
    const connectOnlyBackend = String(process.env.B_DESKTOP_005_BACKEND_ORIGIN || '').trim();

    const host = '127.0.0.1';
    let backendOrigin = null;
    let frontendUrl = null;
    let backendPort = null;
    let frontendPort = null;

    const webuiDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'webui-dist');
    const productDistDir = path.join(REPO_ROOT, 'apps', 'desktop-electron', 'resources', 'product-dist');
    const webuiIndex = path.join(webuiDistDir, 'index.html');
    const productIndex = path.join(productDistDir, 'index.html');

    if (!fs.existsSync(webuiIndex)) {
      evidence.reason = `BLOCKED: missing WebUI dist (${webuiIndex}). Run: npm run desktop:electron:sync-webui`;
      await finalize('BLOCKED', evidence.reason);
      process.exit(2);
      return;
    }
    if (!fs.existsSync(productIndex)) {
      evidence.reason = `BLOCKED: missing Product Shell dist (${productIndex}).`;
      await finalize('BLOCKED', evidence.reason);
      process.exit(2);
      return;
    }

    if (connectOnlyFrontend) {
      evidence.run.mode = 'connect-only';
      frontendUrl = connectOnlyFrontend.endsWith('/') ? connectOnlyFrontend : `${connectOnlyFrontend}/`;
      backendOrigin = connectOnlyBackend || null;
      evidence.proxy = { url: frontendUrl, connect_only: true };
      evidence.backend = backendOrigin ? { origin: backendOrigin, connect_only: true } : { connect_only: true };
    } else {
      evidence.run.mode = 'boot-backend-and-proxy';
      backendPort = await getFreePort(host);
      frontendPort = await getFreePort(host);
      backendOrigin = `http://${host}:${backendPort}`;

      // Start backend from source (deterministic + avoids running bundled binaries in restricted environments).
      // Matches apps/webui/playwright.config.ts backend command style.
      const backendCmd = 'python3';
      const backendArgs = [
        '-m',
        'uvicorn',
        'octopusos.webui.app:app',
        '--host',
        host,
        '--port',
        String(backendPort),
      ];

      const backendEnv = { ...process.env };
      backendEnv.OCTOPUSOS_COMPAT_DEMO = backendEnv.OCTOPUSOS_COMPAT_DEMO || '1';

      backendProc = spawn(backendCmd, backendArgs, {
        stdio: ['ignore', 'pipe', 'pipe'],
        env: backendEnv,
        cwd: REPO_ROOT,
        windowsHide: true,
      });

      const backendStderr = [];
      backendProc.stderr.on('data', (d) => backendStderr.push(String(d)));

      evidence.backend = {
        origin: backendOrigin,
        command: [backendCmd, ...backendArgs].join(' '),
        pid: backendProc.pid || null,
        env: {
          OCTOPUSOS_COMPAT_DEMO: backendEnv.OCTOPUSOS_COMPAT_DEMO,
        },
      };

      const health = await waitForHealth(backendOrigin, 45_000);
      if (!health.ok) {
        const tail = backendStderr.join('').split('\n').slice(-40).join('\n').trim();
        evidence.reason = `BLOCKED: backend did not become healthy at ${backendOrigin}/api/health`;
        evidence.backend.health = { ok: false };
        evidence.backend.stderr_tail = tail || null;
        await cleanup();
        await finalize('BLOCKED', evidence.reason);
        process.exit(2);
        return;
      }
      evidence.backend.health = { ok: true, payload: health.health };

      // Start Desktop proxy server (same implementation as Electron uses).
      const { startWebuiProxyServer } = getDesktopProxyModule();
      proxyServer = await startWebuiProxyServer({
        host,
        port: frontendPort,
        webuiDistDir,
        productDistDir,
        backendOrigin,
      });
      frontendUrl = `${proxyServer.url}/`;
      evidence.proxy = {
        url: frontendUrl,
        host,
        port: frontendPort,
        webuiDistDir,
        productDistDir,
      };
    }

    const chromium = getPlaywrightChromium();
    // Prefer a persistent profile for Desktop-style auth stability (repo AGENTS.md).
    let profileDir = String(process.env.PLAYWRIGHT_PROFILE_DIR || '/Users/pangge/.octopusos/playwright-profile').trim();
    try {
      await ensureDir(profileDir);
    } catch {
      profileDir = path.join(REPO_ROOT, '.tmp', 'playwright-profile');
      await ensureDir(profileDir);
    }
    evidence.run.playwright_profile_dir = profileDir;

    pwContext = await chromium.launchPersistentContext(profileDir, { headless: true });
    const page = await pwContext.newPage();

    // Global capture (top-level + iframe console is surfaced here too).
    page.on('console', (msg) => {
      const type = msg.type();
      if (type !== 'error') return;
      const txt = msg.text() || '';
      const loc = msg.location && typeof msg.location === 'function' ? msg.location() : null;
      const entry = {
        ts: isoNow(),
        type,
        text: txt,
        url: loc && loc.url ? loc.url : null,
        line: loc && typeof loc.lineNumber === 'number' ? loc.lineNumber : null,
        column: loc && typeof loc.columnNumber === 'number' ? loc.columnNumber : null,
        is_404: /\\b404\\b/.test(txt) || /Failed to load resource/i.test(txt),
      };
      evidence.console.errors.push(entry);
    });
    page.on('pageerror', (err) => {
      evidence.console.pageerrors.push({ ts: isoNow(), message: String(err && err.message ? err.message : err) });
    });
    page.on('requestfailed', (req) => {
      const url = req.url();
      evidence.network.requestfailed.push({
        ts: isoNow(),
        url,
        method: req.method(),
        failure: req.failure() ? req.failure().errorText : null,
      });
    });
    page.on('response', (resp) => {
      const status = resp.status();
      if (status < 400) return;
      const url = resp.url();
      if (status === 404 && isIgnorable404(url)) return;
      evidence.network.responses_4xx_5xx.push({
        ts: isoNow(),
        url,
        status,
        request_method: resp.request().method(),
      });
    });

    // Load Product Shell (root serves product-dist index.html).
    await page.goto(frontendUrl, { waitUntil: 'domcontentloaded', timeout: 20_000 });
    await page.waitForSelector('.shell', { timeout: 20_000 });

    const tabs = getProductShellTabsFromRepoEvidence();
    for (const t of tabs) {
      const tabEvidence = {
        label: t.label,
        hashRoute: t.hashRoute,
        expected_iframe_src: `/console${t.consolePath}?embed=1`,
        iframe_src: null,
        iframe_doc_status: null,
        console_errors_during_tab: [],
        network_4xx_5xx_during_tab: [],
      };

      // Snapshot current global counts so we can attribute deltas.
      const consoleStart = evidence.console.errors.length;
      const netStart = evidence.network.responses_4xx_5xx.length;

      // Click nav item.
      await page.locator('.nav a', { hasText: t.label }).click({ timeout: 10_000 });

      // Wait for iframe src update and the iframe document response.
      const iframe = page.locator('iframe.embedFrame');
      await iframe.waitFor({ state: 'visible', timeout: 15_000 });
      await page.waitForFunction(
        (expected) => {
          const el = document.querySelector('iframe.embedFrame');
          return !!el && el.getAttribute('src') === expected;
        },
        tabEvidence.expected_iframe_src,
        { timeout: 15_000 },
      );
      tabEvidence.iframe_src = await iframe.getAttribute('src');

      // Ensure the route document under /console/* is not a 404.
      const expectedAbs = new URL(tabEvidence.expected_iframe_src, frontendUrl).toString();
      const resp = await page.waitForResponse(
        (r) => r.url() === expectedAbs && r.request().resourceType() === 'document',
        { timeout: 15_000 },
      ).catch(() => null);
      tabEvidence.iframe_doc_status = resp ? resp.status() : null;

      // Give Console a moment to execute route bootstrapping and surface any late 404 resource errors.
      await sleep(1200);

      tabEvidence.console_errors_during_tab = evidence.console.errors.slice(consoleStart);
      tabEvidence.network_4xx_5xx_during_tab = evidence.network.responses_4xx_5xx.slice(netStart);
      evidence.tabs.push(tabEvidence);

      // Fail fast if the embedded Console route itself is not OK.
      if (tabEvidence.iframe_doc_status && tabEvidence.iframe_doc_status >= 400) {
        throw new Error(`Embedded console route failed for "${t.label}": ${expectedAbs} -> ${tabEvidence.iframe_doc_status}`);
      }
    }

    const has404ConsoleError = evidence.console.errors.some((e) => e.is_404 && !isIgnorable404(e.url || ''));
    if (has404ConsoleError) {
      await cleanup();
      await finalize('FAIL', 'Console has 404-style errors while loading embedded Console routes');
      process.exit(1);
      return;
    }

    // If there are any other console errors or page errors, consider it FAIL for this smoke (deterministic).
    if (evidence.console.errors.length > 0 || evidence.console.pageerrors.length > 0) {
      await cleanup();
      await finalize('FAIL', 'Console/page errors detected while loading Product Shell embedded Console routes');
      process.exit(1);
      return;
    }

    await cleanup();
    await finalize('PASS', null);
    process.exit(0);
  } catch (err) {
    const msg = String((err && err.stack) || err);
    evidence.run.error = msg;
    await cleanup();
    // Common restricted-sandbox failure: cannot bind/listen on loopback.
    if (/\blisten\b/i.test(msg) && /\bEPERM\b/.test(msg)) {
      const hint = [
        'BLOCKED: environment forbids binding local ports (listen EPERM).',
        'Run this on a normal host OS, or set:',
        '  B_DESKTOP_005_FRONTEND_URL=http://<running-desktop-proxy-host>:<port>',
        '  B_DESKTOP_005_BACKEND_ORIGIN=http://<backend-host>:<port> (optional)',
      ].join(' ');
      await finalize('BLOCKED', hint);
      process.exit(2);
      return;
    }
    await finalize('FAIL', msg);
    process.exit(1);
  }
}

// eslint-disable-next-line no-void
void main();
