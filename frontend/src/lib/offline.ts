/**
 * Offline support utilities.
 * Caches sequence data in localStorage after import.
 * Queues mutations made offline and replays them on reconnect.
 */

const CACHE_PREFIX = 'bidpilot_cache_';
const QUEUE_KEY = 'bidpilot_offline_queue';

export function isOnline(): boolean {
  return navigator.onLine;
}

// ── Cache ────────────────────────────────────────────────────────────────

export function cacheData(key: string, data: unknown): void {
  try {
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(data));
  } catch {
    // localStorage full — silently fail
  }
}

export function getCachedData<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + key);
    return raw ? JSON.parse(raw) as T : null;
  } catch {
    return null;
  }
}

export function clearCache(key: string): void {
  localStorage.removeItem(CACHE_PREFIX + key);
}

// ── Mutation Queue ───────────────────────────────────────────────────────

interface QueuedMutation {
  id: string;
  method: 'POST' | 'PUT' | 'DELETE';
  url: string;
  body?: unknown;
  timestamp: number;
}

export function queueMutation(method: QueuedMutation['method'], url: string, body?: unknown): void {
  const queue = getQueue();
  queue.push({
    id: crypto.randomUUID(),
    method,
    url,
    body,
    timestamp: Date.now(),
  });
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

export function getQueue(): QueuedMutation[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function clearQueue(): void {
  localStorage.removeItem(QUEUE_KEY);
}

export function getQueueLength(): number {
  return getQueue().length;
}

// ── Online/Offline listeners ─────────────────────────────────────────────

type StatusCallback = (online: boolean) => void;
const listeners: StatusCallback[] = [];

export function onStatusChange(cb: StatusCallback): () => void {
  listeners.push(cb);
  return () => {
    const idx = listeners.indexOf(cb);
    if (idx >= 0) listeners.splice(idx, 1);
  };
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => listeners.forEach((cb) => cb(true)));
  window.addEventListener('offline', () => listeners.forEach((cb) => cb(false)));
}
