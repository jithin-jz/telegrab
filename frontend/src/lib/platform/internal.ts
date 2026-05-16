/**
 * Internal pywebview helpers.
 *
 * pywebview injects `window.pywebview.api` after the page loads, asynchronously.
 * Code that runs early (e.g. App.tsx initialization) might call into the API
 * before it's ready, so we wrap every call in a small wait-and-retry helper.
 *
 * The event bus is created eagerly here so Python's `evaluate_js` dispatches
 * always have somewhere to land — even before app.py's bootstrap script runs,
 * and across Vite HMR reloads.
 */

interface PyWebviewApi {
  [name: string]: (args?: unknown) => Promise<unknown>;
}

interface EventBus {
  subscribe: (
    event: string,
    cb: (e: { event: string; payload: unknown }) => void
  ) => () => void;
  dispatch: (event: string, payload: unknown) => void;
}

interface PyWebviewWindow extends Window {
  pywebview?: { api?: PyWebviewApi };
  __tgDriveBus?: EventBus;
  // Components written for the Tauri build sometimes guard their logic
  // with `'__TAURI_INTERNALS__' in window` to detect a real desktop env.
  // We expose a stub here so those guards pass under pywebview.
  __TAURI_INTERNALS__?: Record<string, unknown>;
}

const w = window as PyWebviewWindow;

// Tell the existing AuthWizard / similar guards we're in a desktop shell.
if (!w.__TAURI_INTERNALS__) {
  w.__TAURI_INTERNALS__ = { runtime: "pywebview" };
}

// Eagerly create the event bus so Python ↔ JS event dispatch never misses.
function ensureBus(): EventBus {
  if (w.__tgDriveBus) return w.__tgDriveBus;

  const listeners = new Map<string, Set<(e: { event: string; payload: unknown }) => void>>();
  const bus: EventBus = {
    subscribe(event, cb) {
      let s = listeners.get(event);
      if (!s) {
        s = new Set();
        listeners.set(event, s);
      }
      s.add(cb);
      return () => s!.delete(cb);
    },
    dispatch(event, payload) {
      const s = listeners.get(event);
      if (!s) return;
      for (const cb of s) {
        try {
          cb({ event, payload });
        } catch (e) {
          console.error('event callback failed', e);
        }
      }
    },
  };
  w.__tgDriveBus = bus;
  return bus;
}

// Bus exists from the moment this module is imported.
ensureBus();

const READY_TIMEOUT_MS = 10_000;

let readyPromise: Promise<PyWebviewApi> | null = null;

function awaitApi(): Promise<PyWebviewApi> {
  if (readyPromise) return readyPromise;

  readyPromise = new Promise((resolve, reject) => {
    if (w.pywebview?.api) {
      resolve(w.pywebview.api);
      return;
    }

    const start = Date.now();
    const interval = setInterval(() => {
      if (w.pywebview?.api) {
        clearInterval(interval);
        resolve(w.pywebview.api);
        return;
      }
      if (Date.now() - start > READY_TIMEOUT_MS) {
        clearInterval(interval);
        reject(new Error('pywebview API never became available'));
      }
    }, 50);

    // Native event pywebview fires when ready.
    window.addEventListener(
      'pywebviewready',
      () => {
        if (w.pywebview?.api) {
          clearInterval(interval);
          resolve(w.pywebview.api);
        }
      },
      { once: true }
    );
  });

  return readyPromise;
}

/**
 * Call a Python bridge method by name. Always passes a single args object
 * (matching the Tauri `invoke(cmd, args)` convention).
 */
export async function callPy<T = unknown>(
  method: string,
  args?: Record<string, unknown>
): Promise<T> {
  const api = await awaitApi();
  const fn = api[method];
  if (typeof fn !== 'function') {
    throw new Error(`Python method not exposed: ${method}`);
  }
  // pywebview returns a Promise that resolves with the Python return value
  // or rejects with an Error containing the Python exception string.
  return (await fn(args ?? {})) as T;
}

/** Lazy accessor for the event bus the Python EventBus dispatches into. */
export function getBus(): EventBus {
  return ensureBus();
}
