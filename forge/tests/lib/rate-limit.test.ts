import { describe, expect, test } from "bun:test";
import { checkRateLimit } from "../../src/lib/rate-limit";

describe("checkRateLimit", () => {
  // Use unique keys per test to avoid cross-test contamination
  // (the rate limiter uses a module-level Map)

  test("allows requests under the limit", () => {
    const key = "rate-test-under-limit";
    expect(checkRateLimit(key, 3, 60_000)).toBe(true);
    expect(checkRateLimit(key, 3, 60_000)).toBe(true);
    expect(checkRateLimit(key, 3, 60_000)).toBe(true);
  });

  test("blocks requests at the limit", () => {
    const key = "rate-test-at-limit";
    checkRateLimit(key, 2, 60_000);
    checkRateLimit(key, 2, 60_000);
    expect(checkRateLimit(key, 2, 60_000)).toBe(false);
  });

  test("allows requests after window expires", async () => {
    const key = "rate-test-expired";
    const windowMs = 50; // 50ms window for fast testing

    checkRateLimit(key, 1, windowMs);
    expect(checkRateLimit(key, 1, windowMs)).toBe(false);

    // Wait for window to expire
    await new Promise((resolve) => setTimeout(resolve, windowMs + 10));

    expect(checkRateLimit(key, 1, windowMs)).toBe(true);
  });

  test("tracks different keys independently", () => {
    const key1 = "rate-test-key-a";
    const key2 = "rate-test-key-b";

    checkRateLimit(key1, 1, 60_000);
    expect(checkRateLimit(key1, 1, 60_000)).toBe(false); // key1 blocked

    expect(checkRateLimit(key2, 1, 60_000)).toBe(true); // key2 still allowed
  });

  test("handles limit of 0 (always reject)", () => {
    const key = "rate-test-zero-limit";
    expect(checkRateLimit(key, 0, 60_000)).toBe(false);
  });

  test("evicts expired entries to prevent unbounded growth", async () => {
    const windowMs = 50; // 50ms window for fast testing
    // Fill multiple keys
    for (let i = 0; i < 150; i++) {
      checkRateLimit(`eviction-test-${i}`, 10, windowMs);
    }

    // Wait for window to expire
    await new Promise((resolve) => setTimeout(resolve, windowMs + 20));

    // Trigger more calls to force eviction
    for (let i = 0; i < 150; i++) {
      checkRateLimit(`eviction-trigger-${i}`, 10, windowMs);
    }

    // The store should have evicted the expired keys
    // We can verify by checking that the old keys are no longer rate-limited
    // (their timestamps were cleaned up)
    expect(checkRateLimit("eviction-test-0", 1, windowMs)).toBe(true);

    // Verify store size is bounded — exported for testing
    const { _getStoreSize } = await import("../../src/lib/rate-limit");
    // Should be around 150 (new trigger keys) + 1 (just added), not 300+
    expect(_getStoreSize()).toBeLessThan(200);
  });
});
