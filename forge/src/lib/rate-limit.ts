/**
 * Simple in-memory sliding-window rate limiter.
 * Tracks timestamps per key (user ID) and rejects if too many in the window.
 * Stores the window duration per key so eviction respects each limiter's window.
 * Resets on server restart — good enough for local dev.
 */

const store = new Map<string, { timestamps: number[]; windowMs: number }>();
let callCount = 0;

export function checkRateLimit(
  key: string,
  maxRequests: number,
  windowMs: number
): boolean {
  callCount++;
  if (callCount % 100 === 0) evictExpired();

  const now = Date.now();
  const entry = store.get(key);
  const timestamps = entry?.timestamps ?? [];

  // Prune expired timestamps
  const valid = timestamps.filter((t) => now - t < windowMs);

  if (valid.length >= maxRequests) {
    store.set(key, { timestamps: valid, windowMs });
    return false; // rate limited
  }

  valid.push(now);
  store.set(key, { timestamps: valid, windowMs });
  return true; // allowed
}

function evictExpired(): void {
  const now = Date.now();
  for (const [key, entry] of store) {
    const valid = entry.timestamps.filter((t) => now - t < entry.windowMs);
    if (valid.length === 0) {
      store.delete(key);
    } else {
      store.set(key, { timestamps: valid, windowMs: entry.windowMs });
    }
  }
}

/** Exposed for testing only — returns the number of keys in the store. */
export function _getStoreSize(): number {
  return store.size;
}

/** Clear all rate limit entries. Used by E2E test fixtures to reset state between tests. */
export function resetRateLimits(): void {
  store.clear();
}
