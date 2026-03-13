/**
 * Simple in-memory sliding-window rate limiter.
 * Tracks timestamps per key (user ID) and rejects if too many in the window.
 * Resets on server restart — good enough for local dev.
 */

const store = new Map<string, number[]>();
let callCount = 0;

export function checkRateLimit(
  key: string,
  maxRequests: number,
  windowMs: number
): boolean {
  callCount++;
  if (callCount % 100 === 0) evictExpired(windowMs);

  const now = Date.now();
  const timestamps = store.get(key) ?? [];

  // Prune expired timestamps
  const valid = timestamps.filter((t) => now - t < windowMs);

  if (valid.length >= maxRequests) {
    store.set(key, valid);
    return false; // rate limited
  }

  valid.push(now);
  store.set(key, valid);
  return true; // allowed
}

function evictExpired(windowMs: number): void {
  const now = Date.now();
  for (const [key, timestamps] of store) {
    const valid = timestamps.filter((t) => now - t < windowMs);
    if (valid.length === 0) {
      store.delete(key);
    } else {
      store.set(key, valid);
    }
  }
}

/** Exposed for testing only — returns the number of keys in the store. */
export function _getStoreSize(): number {
  return store.size;
}
