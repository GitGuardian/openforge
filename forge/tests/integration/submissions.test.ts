import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { anonFetch, authFetch, createTestUser, deleteTestUser } from "./helpers";

describe("Submissions (integration)", () => {
  let token: string;
  let userId: string;

  beforeAll(async () => {
    const user = await createTestUser();
    token = user.accessToken;
    userId = user.userId;
  });

  afterAll(async () => {
    if (userId) await deleteTestUser(userId);
  });

  test("POST /api/submissions without auth returns 401", async () => {
    const res = await anonFetch("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/test/repo" }),
    });
    expect(res.status).toBe(401);
  });

  test("POST /api/submissions with invalid gitUrl returns 400", async () => {
    const res = await authFetch("/api/submissions", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "not-a-url" }),
    });
    expect(res.status).toBe(400);
  });

  test("POST /api/submissions creates a submission", async () => {
    const uniqueUrl = `https://github.com/integ-test/plugin-${Date.now()}`;
    const res = await authFetch("/api/submissions", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        gitUrl: uniqueUrl,
        description: "Integration test submission",
      }),
    });
    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.id).toBeTruthy();
    expect(data.gitUrl).toBe(uniqueUrl);
    expect(data.status).toBe("pending");
  });

  test("GET /api/submissions returns submissions list for authenticated user", async () => {
    const res = await authFetch("/api/submissions", token);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
  });

  test("GET /api/submissions without auth returns 401", async () => {
    const res = await anonFetch("/api/submissions");
    expect(res.status).toBe(401);
  });

  test("POST /api/submissions duplicate pending URL returns 409", async () => {
    const uniqueUrl = `https://github.com/integ-dup/plugin-${Date.now()}`;
    // Create first
    await authFetch("/api/submissions", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: uniqueUrl }),
    });
    // Duplicate
    const res = await authFetch("/api/submissions", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: uniqueUrl }),
    });
    expect(res.status).toBe(409);
  });
});
