import { useEffect, useRef } from 'react';

interface QueueEntry {
  id: string;
  status: string;
}

/**
 * Remove successfully finished items `seconds` after they finish
 * (Settings → Transfers → "Clear finished transfers"). 0 disables it.
 */
export function useAutoClearFinished<T extends QueueEntry>(
  queue: T[],
  setQueue: (update: (q: T[]) => T[]) => void,
  seconds: number,
): void {
  const scheduled = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    if (!seconds || seconds <= 0) return;
    for (const item of queue) {
      if (item.status !== 'success' || scheduled.current.has(item.id)) continue;
      const timer = setTimeout(() => {
        scheduled.current.delete(item.id);
        setQueue((q) => q.filter((i) => !(i.id === item.id && i.status === 'success')));
      }, seconds * 1000);
      scheduled.current.set(item.id, timer);
    }
  }, [queue, seconds, setQueue]);

  useEffect(() => {
    const timers = scheduled.current;
    return () => {
      timers.forEach((t) => clearTimeout(t));
      timers.clear();
    };
  }, []);
}

/**
 * Call `onIdle(n)` once the queue goes from busy to idle, where `n` is the
 * number of items that succeeded during that busy period. Keeps bulk
 * transfers to a single notification instead of one per file.
 */
export function useNotifyWhenIdle<T extends QueueEntry>(
  queue: T[],
  activeStatus: string,
  onIdle: (succeeded: number) => void,
): void {
  const wasBusy = useRef(false);
  const succeededAtStart = useRef<Set<string>>(new Set());
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;

  useEffect(() => {
    const busy = queue.some((i) => i.status === 'pending' || i.status === activeStatus);
    if (busy && !wasBusy.current) {
      succeededAtStart.current = new Set(queue.filter((i) => i.status === 'success').map((i) => i.id));
    }
    if (!busy && wasBusy.current) {
      const done = queue.filter(
        (i) => i.status === 'success' && !succeededAtStart.current.has(i.id)
      ).length;
      if (done > 0) onIdleRef.current(done);
    }
    wasBusy.current = busy;
  }, [queue, activeStatus]);
}
