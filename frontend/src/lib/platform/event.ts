/**
 * Shim for `@tauri-apps/api/event`.
 *
 * The Python EventBus (see `telegrab/events.py`) dispatches events through
 * the bootstrap-injected `window.__telegrabBus`. We expose the same
 * `listen` API the Tauri code is written against.
 */

import { getBus } from './internal';

export type EventCallback<T> = (event: { event: string; payload: T }) => void;
export type UnlistenFn = () => void;

export function listen<T = unknown>(event: string, cb: EventCallback<T>): Promise<UnlistenFn> {
  const bus = getBus();
  const unsubscribe = bus.subscribe(event, (e) => cb(e as { event: string; payload: T }));
  return Promise.resolve(unsubscribe);
}

export function once<T = unknown>(event: string, cb: EventCallback<T>): Promise<UnlistenFn> {
  return listen<T>(event, (e) => {
    cb(e);
    // Self-unsubscribe by returning the unlisten on the next tick.
    queueMicrotask(() => unlistenRef?.());
  }).then((un) => {
    unlistenRef = un;
    return un;
  });
  // eslint-disable-next-line prefer-const
  var unlistenRef: UnlistenFn | undefined;
}

/**
 * `emit` was used in the original Tauri app to fire events from JS to JS.
 * We don't need cross-window broadcasting, so this just dispatches locally.
 */
export function emit<T = unknown>(event: string, payload?: T): Promise<void> {
  getBus().dispatch(event, payload);
  return Promise.resolve();
}
