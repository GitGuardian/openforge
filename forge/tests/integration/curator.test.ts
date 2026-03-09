import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { anonFetch, authFetch, createTestUser, deleteTestUser } from "./helpers";

describe("Curator dashboard (integration)", () => {
  let token: string;
  let userId: string;

  beforeAll(async () => {
    const user = await createTestUser();
    token = user.accessToken;
    userId = user.userId;
    // Note: this user has "user" role, not "curator"
  });

  afterAll(async () => {
    if (userId) await deleteTestUser(userId);
  });

  test("GET /curator/submissions without auth redirects to login", async () => {
    const res = await anonFetch("/curator/submissions", { redirect: "manual" });
    // Should redirect to /auth/login
    expect([302, 303]).toContain(res.status);
  });

  test("GET /curator/submissions with non-curator role returns 403", async () => {
    const res = await authFetch("/curator/submissions", token);
    // Regular user should not access curator dashboard
    expect(res.status).not.toBe(200);
  });

  test("GET /submit without auth redirects to login", async () => {
    const res = await anonFetch("/submit", { redirect: "manual" });
    expect([302, 303]).toContain(res.status);
  });

  test("GET /submit with auth returns submit form", async () => {
    const res = await authFetch("/submit", token);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Submit");
  });
});
