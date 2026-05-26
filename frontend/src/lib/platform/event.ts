/**
 * Desktop platform event bus.
 *
 * The Python EventBus (see `telegrab/events.py`) dispatches events through
 * the bootstrap-injected `window.__telegrabBus`. We expose `listen`, `once`,
 * and `emit` APIs for cross-layer event handling.
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
  let unlistenRef: UnlistenFn | undefined;
  const unlisten = listen<T>(event, (e) => {
    cb(e);
    queueMicrotask(() => unlistenRef?.());
  });
  return unlisten.then((un) => {
    unlistenRef = un;
    return un;
  });
}

/**
 * `emit` was used in the original Tauri app to fire events from JS to JS.
 * We don't need cross-window broadcasting, so this just dispatches locally.
 */
export function emit<T = unknown>(event: string, payload?: T): Promise<void> {
  getBus().dispatch(event, payload);
  return Promise.resolve();
}
