import { app, BrowserWindow, Menu, Tray, ipcMain, dialog, nativeImage } from 'electron';
import path from 'node:path';
import fs from 'node:fs';
import { ensureAdminToken } from './util/adminToken';
import { ensureDir, logsDir, webuiDistDir } from './util/paths';
import { logMain } from './util/log';
import { startWebuiProxyServer, type ProxyServer } from './proxyServer';
import { startOllamaRequired, startRuntimeBackend, stopSidecar, type SidecarProcess } from './sidecars';
import { findFreePort, isPortFree } from './util/ports';
import { isOllamaListening, waitForOllama } from './ollamaControl';

const HOST = '127.0.0.1';
const PREFERRED_BACKEND_PORT = 8080;
const PREFERRED_FRONTEND_PORT = 1420;
const PREFERRED_OLLAMA_PORT = 11434;

let tray: Tray | null = null;
let mainWindow: BrowserWindow | null = null;
let consoleWindow: BrowserWindow | null = null;
let proxy: ProxyServer | null = null;
let backend: SidecarProcess | null = null;
let ollama: SidecarProcess | null = null;
let adminToken: string | null = null;
let frontendUrl: string | null = null;
let ollamaBaseUrl: string | null = null;

async function waitForBackendHealth(baseOrigin: string, timeoutMs: number): Promise<void> {
  const url = `${baseOrigin}/api/health`;
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 800);
      const resp = await fetch(url, { method: 'GET', signal: controller.signal });
      clearTimeout(timer);
      if (resp.ok) return;
    } catch {
      // ignore
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`Backend did not become healthy within ${Math.round(timeoutMs / 1000)}s (${url})`);
}

function createWindow(url: string): BrowserWindow {
  const preloadPath = path.join(__dirname, 'preload.js');
  const win = new BrowserWindow({
    width: 1920,
    height: 1080,
    minWidth: 1920,
    minHeight: 1080,
    show: false,
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.once('ready-to-show', () => win.show());
  void win.loadURL(url);
  return win;
}

function setTrayStatus(label: string): void {
  tray?.setToolTip(`OctopusOS\n${label}`);
}

function buildTrayMenu(): void {
  if (!tray) return;
  const menu = Menu.buildFromTemplate([
    {
      label: 'Open OctopusOS',
      click: async () => {
        if (frontendUrl) {
          if (!mainWindow) mainWindow = createWindow(frontendUrl);
          else {
            mainWindow.show();
            mainWindow.focus();
          }
        }
      },
    },
    {
      label: 'Open System Console',
      click: async () => {
        if (!frontendUrl) return;
        await openSystemConsoleWindow();
      },
    },
    {
      label: backend ? 'Restart' : 'Start',
      click: async () => {
        await startStack();
      },
    },
    {
      label: 'Stop',
      enabled: !!backend,
      click: async () => {
        await stopStack();
      },
    },
    { type: 'separator' },
    {
      label: 'View Logs Folder',
      click: async () => {
        ensureDir(logsDir());
        await dialog.showMessageBox({
          type: 'info',
          message: 'Logs location',
          detail: logsDir(),
        });
      },
    },
    { type: 'separator' },
    { role: 'quit', label: 'Quit' },
  ]);
  tray.setContextMenu(menu);
}

async function startStack(): Promise<void> {
  if (backend && proxy) {
    setTrayStatus('Running');
    buildTrayMenu();
    return;
  }

  try {
    logMain('startStack begin', { packaged: app.isPackaged });
    setTrayStatus('Starting...');
    buildTrayMenu();

    adminToken = ensureAdminToken();

    const backendPort = await findFreePort(HOST, PREFERRED_BACKEND_PORT);
    const frontendPort = await findFreePort(HOST, PREFERRED_FRONTEND_PORT);
    logMain('ports selected', { backendPort, frontendPort });

    // Ollama is required: use an existing instance if it is already listening on the default port;
    // otherwise start our bundled sidecar (or auto-download if missing).
    setTrayStatus('Starting Ollama...');
    buildTrayMenu();
    const defaultOllamaUrl = `http://${HOST}:${PREFERRED_OLLAMA_PORT}`;
    if (await isOllamaListening(defaultOllamaUrl)) {
      logMain('ollama already listening', { url: defaultOllamaUrl });
      ollamaBaseUrl = defaultOllamaUrl;
    } else {
      const selectedPort = (await isPortFree(HOST, PREFERRED_OLLAMA_PORT))
        ? PREFERRED_OLLAMA_PORT
        : await findFreePort(HOST, PREFERRED_OLLAMA_PORT);
      logMain('starting ollama sidecar', { port: selectedPort });
      const started = await startOllamaRequired({ port: selectedPort });
      ollama = started.proc;
      ollamaBaseUrl = started.baseUrl;
      await waitForOllama(ollamaBaseUrl, 45_000);
    }

    setTrayStatus('Starting Backend...');
    buildTrayMenu();
    logMain('starting backend', { backendPort, ollamaBaseUrl });
    backend = await startRuntimeBackend({
      host: HOST,
      port: backendPort,
      adminToken,
      ollamaBaseUrl: ollamaBaseUrl || defaultOllamaUrl,
    });

    const backendOrigin = `http://${HOST}:${backendPort}`;
    setTrayStatus('Waiting for API...');
    buildTrayMenu();
    logMain('waiting for backend health', { backendOrigin });
    await waitForBackendHealth(backendOrigin, 45_000);
    logMain('backend healthy', { backendOrigin });

    const distDir = webuiDistDir();
    const productDistDir = path.join(distDir, '..', 'product-dist');
    setTrayStatus('Starting UI...');
    buildTrayMenu();
    logMain('starting proxy', { distDir, productDistDir });
    proxy = await startWebuiProxyServer({
      host: HOST,
      port: frontendPort,
      webuiDistDir: distDir,
      productDistDir,
      backendOrigin,
    });

    frontendUrl = `${proxy.url}/`;
    setTrayStatus(`Running: ${frontendUrl}`);
    logMain('running', { frontendUrl });

    if (!mainWindow) mainWindow = createWindow(frontendUrl);
    else {
      void mainWindow.loadURL(frontendUrl);
      mainWindow.show();
    }

    buildTrayMenu();
  } catch (err) {
    logMain('startStack failed', { err: String((err as any)?.stack || err) });
    await stopStack();
    const msg = String((err as any)?.stack || err);
    setTrayStatus('Start failed');
    buildTrayMenu();
    dialog.showErrorBox('OctopusOS Desktop failed to start', msg);
  }
}

async function stopStack(): Promise<void> {
  setTrayStatus('Stopping...');
  buildTrayMenu();
  logMain('stopStack begin');

  try {
    if (proxy) await proxy.close();
  } catch {
    // ignore
  }
  proxy = null;
  frontendUrl = null;

  stopSidecar(backend);
  backend = null;

  stopSidecar(ollama);
  ollama = null;

  setTrayStatus('Stopped');
  buildTrayMenu();
  logMain('stopStack done');
}

async function bootstrap(): Promise<void> {
  // Prevent default app menu (keep things minimal for now).
  Menu.setApplicationMenu(null);

  ensureDir(logsDir());
  logMain('bootstrap');

  adminToken = ensureAdminToken();

  ipcMain.on('octo:getAdminTokenSync', (event) => {
    event.returnValue = adminToken;
  });

  ipcMain.handle('octo:pickRepoDirectory', async () => {
    const res = await dialog.showOpenDialog({
      title: 'Choose a repository folder',
      properties: ['openDirectory'],
    });
    if (res.canceled) return null;
    const p = res.filePaths?.[0];
    return p || null;
  });

  ipcMain.handle('octo:openSystemConsole', async () => {
    await openSystemConsoleWindow();
  });

  // Dock icon (dev). In packaged builds, app icon comes from electron-builder bundle metadata.
  if (process.platform === 'darwin' && app.dock) {
    try {
      app.dock.setIcon(path.join(__dirname, '..', 'assets', 'icon.png'));
    } catch {
      // ignore
    }
  }

  // dist/ is the compiled folder; assets/ is shipped alongside it in the app bundle.
  const trayPath =
    process.platform === 'darwin'
      ? path.join(__dirname, '..', 'assets', 'trayTemplate-mac.png')
      : path.join(__dirname, '..', 'assets', 'trayTemplate.png');
  let trayImage = nativeImage.createFromPath(trayPath);
  if (process.platform === 'darwin') {
    trayImage = trayImage.resize({ width: 18, height: 18 });
    trayImage.setTemplateImage(true);
  }
  tray = new Tray(trayImage);
  tray.on('click', async () => {
    if (!frontendUrl) {
      await startStack();
    } else if (!mainWindow) {
      mainWindow = createWindow(frontendUrl);
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  setTrayStatus('Idle');
  buildTrayMenu();

  await startStack();
}

async function openSystemConsoleWindow(): Promise<void> {
  if (!frontendUrl) return;
  const url = `${frontendUrl.replace(/\/$/, '')}/console/`;
  if (consoleWindow) {
    try {
      await consoleWindow.loadURL(url);
      consoleWindow.show();
      consoleWindow.focus();
      return;
    } catch {
      // ignore
    }
  }
  consoleWindow = createWindow(url);
}

app.on('window-all-closed', () => {
  // Keep the app running in tray even if all windows are closed.
  // (Don't call app.quit() here.)
});

app.on('before-quit', async () => {
  await stopStack();
});

app.whenReady()
  .then(bootstrap)
  .catch(async (err) => {
    await dialog.showErrorBox('OctopusOS Desktop failed to start', String(err?.stack || err));
    app.quit();
  });
