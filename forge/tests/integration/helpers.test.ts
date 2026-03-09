import { describe, expect, test, afterAll } from "bun:test";

// Collect user IDs created during tests so we can clean up
const createdUserIds: string[] = [];

// Import helpers — will fail until helpers.ts exists
const {
  createTestUser,
  authFetch,
  anonFetch,
  deleteTestUser,
  BASE_URL,
  SUPABASE_URL,
  ANON_KEY,
} = await import("./helpers");

afterAll(async () => {
  for (const id of createdUserIds) {
    await deleteTestUser(id);
  }
});

describe("Integration test helpers", () => {
  test("BASE_URL defaults to http://localhost:3000", () => {
    expect(BASE_URL).toBe(process.env.FORGE_URL || "http://localhost:3000");
  });

  test("SUPABASE_URL defaults to http://127.0.0.1:54321", () => {
    expect(SUPABASE_URL).toBe(
      process.env.SUPABASE_URL || "http://127.0.0.1:54321",
    );
  });

  test("ANON_KEY is set from env or .env", () => {
    expect(ANON_KEY).toBeTruthy();
  });

  test("createTestUser() returns accessToken, email, userId", async () => {
    const user = await createTestUser();
    createdUserIds.push(user.userId);

    expect(user.accessToken).toBeTruthy();
    expect(typeof user.accessToken).toBe("string");
    expect(user.email).toContain("@test.local");
    expect(user.userId).toBeTruthy();
    expect(typeof user.userId).toBe("string");
  });

  test("createTestUser() with custom email/password", async () => {
    const email = `custom-${Date.now()}@test.local`;
    const user = await createTestUser(email, "my-custom-password-123!");
    createdUserIds.push(user.userId);

    expect(user.email).toBe(email);
    expect(user.accessToken).toBeTruthy();
  });

  test("anonFetch() hits the real Forge server", async () => {
    const res = await anonFetch("/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  test("authFetch() sends Bearer token header", async () => {
    const user = await createTestUser();
    createdUserIds.push(user.userId);

    // Use the submissions API which requires auth — should NOT get 401
    const res = await authFetch("/api/submissions", user.accessToken);
    expect(res.status).not.toBe(401);
  });

  test("deleteTestUser() removes user without error", async () => {
    const user = await createTestUser();
    // Should not throw
    await deleteTestUser(user.userId);
    // User should no longer be valid — token should fail
    // (Supabase may still honor cached tokens briefly, so just verify no throw)
  });
});
