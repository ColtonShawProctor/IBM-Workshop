import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  cacheData,
  getCachedData,
  clearCache,
  queueMutation,
  getQueue,
  clearQueue,
  getQueueLength,
  isOnline,
  onStatusChange,
} from '../lib/offline';

describe('offline utilities', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('isOnline', () => {
    it('returns navigator.onLine value', () => {
      expect(typeof isOnline()).toBe('boolean');
    });
  });

  describe('cache', () => {
    it('stores and retrieves data', () => {
      cacheData('test_key', { foo: 'bar' });
      const result = getCachedData<{ foo: string }>('test_key');
      expect(result).toEqual({ foo: 'bar' });
    });

    it('returns null for missing key', () => {
      expect(getCachedData('nonexistent')).toBeNull();
    });

    it('clears a specific key', () => {
      cacheData('key1', 'value1');
      cacheData('key2', 'value2');
      clearCache('key1');
      expect(getCachedData('key1')).toBeNull();
      expect(getCachedData('key2')).toBe('value2');
    });

    it('handles non-JSON gracefully', () => {
      localStorage.setItem('bidpilot_cache_bad', '{invalid json');
      expect(getCachedData('bad')).toBeNull();
    });
  });

  describe('mutation queue', () => {
    it('queues and retrieves mutations', () => {
      queueMutation('POST', '/api/bids', { name: 'test' });
      queueMutation('PUT', '/api/bids/1', { name: 'updated' });

      const queue = getQueue();
      expect(queue).toHaveLength(2);
      expect(queue[0].method).toBe('POST');
      expect(queue[0].url).toBe('/api/bids');
      expect(queue[0].body).toEqual({ name: 'test' });
      expect(queue[1].method).toBe('PUT');
    });

    it('reports correct queue length', () => {
      expect(getQueueLength()).toBe(0);
      queueMutation('DELETE', '/api/bids/1');
      expect(getQueueLength()).toBe(1);
    });

    it('clears the queue', () => {
      queueMutation('POST', '/api/test', {});
      clearQueue();
      expect(getQueue()).toHaveLength(0);
    });

    it('each mutation has a unique id and timestamp', () => {
      queueMutation('POST', '/a');
      queueMutation('POST', '/b');
      const queue = getQueue();
      expect(queue[0].id).not.toBe(queue[1].id);
      expect(queue[0].timestamp).toBeLessThanOrEqual(queue[1].timestamp);
    });
  });

  describe('onStatusChange', () => {
    it('returns an unsubscribe function', () => {
      const cb = vi.fn();
      const unsub = onStatusChange(cb);
      expect(typeof unsub).toBe('function');
      unsub();
    });
  });
});
