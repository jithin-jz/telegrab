/**
 * Single source of truth for the app version on the frontend.
 *
 * The actual string is injected at build time by Vite's `define` block
 * from `package.json`. The Python backend exposes the same value via
 * its own `__version__` attribute and the GitHub-based updater compares
 * against it on the server side.
 */
export const APP_VERSION: string = __APP_VERSION__;
