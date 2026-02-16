import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import type net from 'node:net';
import express, { type Request, type Response } from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

export interface ProxyServer {
  close: () => Promise<void>;
  url: string;
}

export function startWebuiProxyServer(opts: {
  host: string;
  port: number;
  webuiDistDir: string;
  productDistDir?: string;
  backendOrigin: string;
}): Promise<ProxyServer> {
  const distDir = opts.webuiDistDir;
  const indexHtml = path.join(distDir, 'index.html');
  if (!fs.existsSync(indexHtml)) {
    throw new Error(`webui dist not found (missing ${indexHtml})`);
  }

  const productDir = (opts.productDistDir || '').trim() || null;
  const productIndex = productDir ? path.join(productDir, 'index.html') : null;
  const hasProduct = Boolean(productIndex && fs.existsSync(productIndex));

  const app = express();

  // Proxy backend first so /api and /ws remain same-origin from the WebUI perspective.
  app.use(
    '/api',
    createProxyMiddleware({
      target: opts.backendOrigin,
      changeOrigin: true,
      secure: false,
      // Express strips the mount path; re-add it so backend receives /api/*.
      pathRewrite: (p) => `/api${p}`,
    }),
  );

  // WebSocket upgrade proxy (do not mount under `/ws` in Express; let the backend see `/ws/*`).
  const wsUpgradeProxy = createProxyMiddleware({
    target: opts.backendOrigin,
    changeOrigin: true,
    secure: false,
    ws: true,
  });

  // Serve WebUI static assets at root paths used by the compiled WebUI build.
  //
  // Why: WebUI v2 build currently emits absolute asset URLs like "/assets/..." and
  // "/octopus-logo.png". When we mount the console under "/console", those absolute URLs
  // would otherwise resolve to the Product UI static server and 404.
  //
  // Keep `index: false` so Product stays in control of "/" and SPA fallback.
  app.use(express.static(distDir, { index: false }));

  // Serve System Console (WebUI) under /console so Product stays clean.
  // Note: we do not expose WebUI at '/' anymore.
  app.use('/console', express.static(distDir, { index: false }));
  app.get('/console/*', (_req: Request, res: Response) => {
    res.sendFile(indexHtml);
  });

  // Serve Product UI at '/' (if present). Otherwise, fall back to Console at root.
  if (hasProduct && productDir && productIndex) {
    app.use(express.static(productDir, { index: false }));
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(productIndex);
    });
  } else {
    app.use(express.static(distDir, { index: false }));

    // SPA fallback (Console as root fallback)
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(indexHtml);
    });
  }

  const server = http.createServer(app);

  // WebSocket proxy support: forward upgrade events explicitly.
  server.on('upgrade', (req, socket, head) => {
    const url = req.url || '';
    if (url.startsWith('/ws')) {
      wsUpgradeProxy.upgrade?.(req, socket as unknown as net.Socket, head);
    } else {
      socket.destroy();
    }
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(opts.port, opts.host, () => {
      const url = `http://${opts.host}:${opts.port}`;
      resolve({
        url,
        close: () =>
          new Promise((r) => {
            server.close(() => r());
          }),
      });
    });
  });
}
