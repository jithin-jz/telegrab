import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import { readFileSync } from 'node:fs';

// Read the app version from package.json so the UI has a single source of
// truth and we don't have to keep version strings in sync across files.
const pkgVersion: string = JSON.parse(
  readFileSync(path.resolve(import.meta.dirname, 'package.json'), 'utf-8'),
).version;

// Content-Security-Policy for the packaged app. Everything is bundled, so
// scripts/styles/fonts only come from the app itself; media and previews
// come from the local streaming server (127.0.0.1, port chosen at runtime).
// Injected only into production builds: the Vite dev server needs inline
// scripts for React Fast Refresh.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'", // wasm: PDF.js image decoders; JS eval stays blocked
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "img-src 'self' data: blob: file: http://127.0.0.1:*",
  "media-src 'self' blob: http://127.0.0.1:*",
  "connect-src 'self' http://127.0.0.1:*",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-src 'none'",
].join('; ');

function contentSecurityPolicy(): Plugin {
  return {
    name: 'telegrab-csp',
    apply: 'build',
    transformIndexHtml: () => [
      {
        tag: 'meta',
        attrs: { 'http-equiv': 'Content-Security-Policy', content: CSP },
        injectTo: 'head-prepend',
      },
    ],
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), contentSecurityPolicy()],

  // Compile-time constants. Replaces `__APP_VERSION__` in source with the
  // version from package.json so the UI doesn't have stale hardcoded strings.
  define: {
    __APP_VERSION__: JSON.stringify(pkgVersion),
  },

  // Use relative asset paths in the built index.html so the bundle works
  // when loaded via `file://` (which is how pywebview opens the production
  // build). Without this, `/assets/index.js` would resolve to the OS root
  // and 404 silently.
  base: './',

  server: {
    port: 5173,
    strictPort: false,
    watch: {
      ignored: ['**/backend/**'],
    },
  },

  build: {
    target: 'es2022',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('pdfjs-dist')) return 'pdf';
          if (id.includes('framer-motion') || id.includes('motion-dom') || id.includes('motion-utils')) return 'motion';
          if (id.includes('@tanstack')) return 'tanstack';
          if (id.includes('react-dom') || id.includes('/react/')) return 'react';
          return 'vendor';
        },
      },
    },
  },
});
