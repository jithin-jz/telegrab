import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import { readFileSync } from 'node:fs';

// Read the app version from package.json so the UI has a single source of
// truth and we don't have to keep `1.4.0` strings in sync across files.
const pkgVersion: string = JSON.parse(
  readFileSync(path.resolve(__dirname, 'package.json'), 'utf-8'),
).version;

// All Tauri SDK imports in the React code resolve to our pywebview-backed
// platform shim under `src/lib/platform/`. The npm packages themselves are
// no longer installed — these aliases are what lets the existing
// `import { invoke } from '@tauri-apps/api/core'` style imports keep working.
const platformShim = (file: string) => path.resolve(__dirname, `src/lib/platform/${file}`);

const tauriShimAliases = {
  '@tauri-apps/api/core': platformShim('core.ts'),
  '@tauri-apps/api/event': platformShim('event.ts'),
  '@tauri-apps/plugin-dialog': platformShim('dialog.ts'),
  '@tauri-apps/plugin-store': platformShim('store.ts'),
  '@tauri-apps/plugin-shell': platformShim('shell.ts'),
  '@tauri-apps/plugin-process': platformShim('process.ts'),
  '@tauri-apps/plugin-updater': platformShim('updater.ts'),
};

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  // Compile-time constants. Replaces `__APP_VERSION__` in source with the
  // version from package.json so the UI doesn't have stale hardcoded strings.
  define: {
    __APP_VERSION__: JSON.stringify(pkgVersion),
  },

  resolve: {
    alias: tauriShimAliases,
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
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('pdfjs-dist')) return 'pdf';
          if (id.includes('framer-motion')) return 'motion';
          if (id.includes('@tanstack')) return 'tanstack';
          return 'vendor';
        },
      },
    },
  },
});
