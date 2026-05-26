import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import { readFileSync } from 'node:fs';

// Read the app version from package.json so the UI has a single source of
// truth and we don't have to keep version strings in sync across files.
const pkgVersion: string = JSON.parse(
  readFileSync(path.resolve(__dirname, 'package.json'), 'utf-8'),
).version;

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

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
