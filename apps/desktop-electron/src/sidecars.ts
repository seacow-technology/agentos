import path from 'node:path';
import fs from 'node:fs';
import { spawn, type ChildProcess } from 'node:child_process';
import crypto from 'node:crypto';
import { app as electronApp } from 'electron';
import { binariesDir, logsDir, ensureDir, appDataDir } from './util/paths';
import { ensureSidecarBinary } from './sidecarEnsure';

export type SidecarKind = 'octopusos-runtime' | 'ollama';

export interface SidecarProcess {
  kind: SidecarKind;
  proc: ChildProcess;
}

function platformExeName(kind: SidecarKind): string {
  if (process.platform === 'win32') {
    if (kind === 'octopusos-runtime') return 'octopusos-runtime.exe';
    if (kind === 'ollama') return 'ollama.exe';
  }
  return kind;
}

function resolveBundledBinary(kind: SidecarKind): string | null {
  const p = path.join(binariesDir(), platformExeName(kind));
  if (fs.existsSync(p)) return p;
  return null;
}

export async function startOllamaRequired(opts: { port: number }): Promise<{ proc: SidecarProcess; port: number; baseUrl: string }> {
  const resolved = await ensureSidecarBinary('ollama');
  const bin = resolved.path;

  ensureDir(logsDir());
  const stderrPath = path.join(logsDir(), 'ollama.stderr.log');
  const stderr = fs.openSync(stderrPath, 'a');

  const env = { ...process.env };
  // Common way to configure Ollama listen address.
  env.OLLAMA_HOST = `127.0.0.1:${opts.port}`;

  const proc = spawn(bin, ['serve'], {
    stdio: ['ignore', 'ignore', stderr],
    env,
    windowsHide: true,
  });

  const baseUrl = `http://127.0.0.1:${opts.port}`;
  return { proc: { kind: 'ollama', proc }, port: opts.port, baseUrl };
}

export async function startRuntimeBackend(opts: {
  host: string;
  port: number;
  adminToken: string;
  ollamaBaseUrl: string;
}): Promise<SidecarProcess> {
  ensureDir(logsDir());
  const stderrPath = path.join(logsDir(), 'desktop-runtime.stderr.log');
  const stderr = fs.openSync(stderrPath, 'a');

  const env = { ...process.env };
  env.OCTOPUSOS_DATA_DIR = path.join(appDataDir(), 'data');
  env.OCTOPUSOS_ADMIN_TOKEN = opts.adminToken;
  // WebUI uses /api/daemon/*; provide a stable per-run token for loopback control endpoints.
  env.OCTOPUSOS_CONTROL_TOKEN = env.OCTOPUSOS_CONTROL_TOKEN || crypto.randomBytes(24).toString('base64url');
  // Point backend's Ollama adapter at the managed Ollama instance.
  env.OLLAMA_HOST = opts.ollamaBaseUrl;

  // Many runtime components resolve storage paths relative to CWD by default (e.g. "store/*.sqlite").
  // Force a writable working directory so "all-in-one" packaged apps work without relying on user shell CWD.
  ensureDir(env.OCTOPUSOS_DATA_DIR);
  const cwd = env.OCTOPUSOS_DATA_DIR;

  let proc: ChildProcess;
  const useBundledInDev = (process.env.OCTOPUSOS_DESKTOP_USE_BUNDLED || '').trim() === '1';
  if (electronApp.isPackaged || useBundledInDev) {
    const runtimeBin = (await ensureSidecarBinary('octopusos-runtime')).path;
    const args = [
      'webui',
      'start',
      '--backend-only',
      '--foreground',
      '--host',
      opts.host,
      '--port',
      String(opts.port),
    ];
    proc = spawn(runtimeBin, args, {
      stdio: ['ignore', 'ignore', stderr],
      env,
      cwd,
      windowsHide: true,
    });
  } else if (!electronApp.isPackaged) {
    // Developer fallback (no bundled runtime yet): run backend directly from source.
    // This keeps iteration moving even before sidecars are built for the platform.
    const repoRoot = path.resolve(electronApp.getAppPath(), '..', '..');
    const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
    const pythonBin = fs.existsSync(venvPython) ? venvPython : 'python3';
    proc = spawn(
      pythonBin,
      ['-m', 'uvicorn', 'octopusos.webui.app:app', '--host', opts.host, '--port', String(opts.port)],
      { stdio: ['ignore', 'ignore', stderr], env, cwd: repoRoot, windowsHide: true },
    );
  } else {
    throw new Error('Bundled octopusos-runtime not found (expected in resources/binaries).');
  }

  return { kind: 'octopusos-runtime', proc };
}

export function stopSidecar(p: SidecarProcess | null): void {
  if (!p) return;
  try {
    p.proc.kill();
  } catch {
    // ignore
  }
}
