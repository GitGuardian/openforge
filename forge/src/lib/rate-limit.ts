/**
 * Simple in-memory sliding-window rate limiter.
 * Tracks timestamps per key (user ID) and rejects if too many in the window.
 * Resets on server restart — good enough for local dev.
 * Replaced by proper middleware in Phase 6 (Hardening).
 */

// Known limitation: keys for inactive users are never evicted, so the store
// grows unboundedly over the lifetime of the process. Acceptable for MVP
// traffic levels; must be replaced with a proper eviction strategy (e.g. LRU
// or external store) in Phase 6 (Hardening).
const store = new Map<string, number[]>();

export function checkRateLimit(
  key: string,
  maxRequests: number,
  windowMs: number
): boolean {
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
