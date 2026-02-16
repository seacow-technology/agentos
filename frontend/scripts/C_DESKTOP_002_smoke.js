/* eslint-disable no-console */
'use strict';

// C_DESKTOP_002: Commercial Scenario - AWS Ops evidence smoke.
//
// Goal (acceptance):
// - Capture evidence for:
//   - GET  /api/mcp/aws/profiles
//   - POST /api/sessions
//   - POST /api/sessions/{id}/messages
// - Store evidence at frontend/reports/e2e_endpoint_evidence/C_DESKTOP_002.json
//
// Implementation notes:
// - Reuse the repo-local generator script (created by Codex during prior iterations)
//   when present: frontend/reports/e2e_endpoint_evidence/generate_C_DESKTOP_002.py
// - This is evidence-first; it exits non-zero if evidence is missing/incomplete.

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const REPO_ROOT = process.cwd();
const GENERATOR = path.join(REPO_ROOT, 'frontend', 'reports', 'e2e_endpoint_evidence', 'generate_C_DESKTOP_002.py');
const EVIDENCE = path.join(REPO_ROOT, 'frontend', 'reports', 'e2e_endpoint_evidence', 'C_DESKTOP_002.json');

function pickPythonExec() {
  const venv = path.join(REPO_ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venv)) return venv;
  if (process.platform === 'darwin') {
    if (fs.existsSync('/opt/homebrew/bin/python3')) return '/opt/homebrew/bin/python3';
    if (fs.existsSync('/usr/local/bin/python3')) return '/usr/local/bin/python3';
  }
  return 'python3';
}

function fail(msg) {
  console.error(`[C_DESKTOP_002] FAIL: ${msg}`);
  process.exitCode = 1;
}

function hasRequiredRequests(evidence) {
  const reqs = Array.isArray(evidence?.requests) ? evidence.requests : [];
  const hit = (method, pathPrefix) =>
    reqs.some((r) => String(r?.method || '').toUpperCase() === method && String(r?.path || '').startsWith(pathPrefix));

  return (
    hit('GET', '/api/mcp/aws/profiles') &&
    hit('POST', '/api/sessions') &&
    hit('POST', '/api/sessions/') && // messages path includes session id
    reqs.some((r) => String(r?.path || '').includes('/messages'))
  );
}

function main() {
  if (!fs.existsSync(GENERATOR)) {
    fail(`missing generator: ${GENERATOR}`);
    return;
  }

  const py = pickPythonExec();
  console.log(`[C_DESKTOP_002] python=${py}`);
  console.log(`[C_DESKTOP_002] generator=${GENERATOR}`);

  const r = spawnSync(py, [GENERATOR], {
    cwd: REPO_ROOT,
    stdio: 'inherit',
    env: process.env,
  });
  if (typeof r.status === 'number' && r.status !== 0) {
    fail(`generator exited with rc=${r.status}`);
    return;
  }

  if (!fs.existsSync(EVIDENCE)) {
    fail(`evidence not found: ${EVIDENCE}`);
    return;
  }

  let data = null;
  try {
    data = JSON.parse(fs.readFileSync(EVIDENCE, 'utf8'));
  } catch (e) {
    fail(`evidence JSON parse failed: ${String(e && e.message ? e.message : e)}`);
    return;
  }

  if (!hasRequiredRequests(data)) {
    fail('evidence missing required requests (profiles/sessions/messages)');
    return;
  }

  console.log(`[C_DESKTOP_002] PASS evidence=${EVIDENCE}`);
}

main();

