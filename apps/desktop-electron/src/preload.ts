import { ipcRenderer } from 'electron';
import { contextBridge } from 'electron';

// Ensure admin token exists in localStorage before the WebUI code runs.
// WebUI expects token under 'octopusos_admin_token'.
try {
  const token = ipcRenderer.sendSync('octo:getAdminTokenSync') as string | null;
  if (token && typeof window !== 'undefined') {
    window.localStorage.setItem('octopusos_admin_token', token);
  }
} catch {
  // Ignore; UI will behave like token not configured.
}

// Minimal Product Shell bridge. Keep this surface tiny: Product should not speak in system APIs.
contextBridge.exposeInMainWorld('octo', {
  getAdminTokenSync: (): string | null => {
    try {
      return (ipcRenderer.sendSync('octo:getAdminTokenSync') as string | null) || null;
    } catch {
      return null;
    }
  },
  pickRepoDirectory: async (): Promise<string | null> => {
    try {
      return (await ipcRenderer.invoke('octo:pickRepoDirectory')) as string | null;
    } catch {
      return null;
    }
  },
  openSystemConsole: async (): Promise<void> => {
    try {
      await ipcRenderer.invoke('octo:openSystemConsole');
    } catch {
      // ignore
    }
  },
});
