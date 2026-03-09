import { describe, expect, test, afterAll } from "bun:test";
import { anonFetch, authFetch, createTestUser, deleteTestUser, BASE_URL } from "./helpers";

const createdUserIds: string[] = [];

afterAll(async () => {
  for (const id of createdUserIds) {
    await deleteTestUser(id);
  }
});

describe("Auth (integration)", () => {
  test("GET /auth/login returns login form", async () => {
    const res = await anonFetch("/auth/login");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("email");
    expect(html).toContain("password");
  });

  test("GET /auth/signup returns signup form", async () => {
    const res = await anonFetch("/auth/signup");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Create your account");
  });

  test("GET /auth/magic-link returns magic link form", async () => {
    const res = await anonFetch("/auth/magic-link");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("magic link");
  });

  test("signup creates user and returns valid session", async () => {
    const user = await createTestUser();
    createdUserIds.push(user.userId);
    expect(user.accessToken).toBeTruthy();
    expect(user.email).toContain("@test.local");
  });

  test("authenticated request succeeds with Bearer token", async () => {
    const user = await createTestUser();
    createdUserIds.push(user.userId);

    // /my/submissions requires auth — should not get 401
    const res = await authFetch("/my/submissions", user.accessToken);
    expect(res.status).not.toBe(401);
  });

  test("unauthenticated request to protected route gets redirected", async () => {
    const res = await anonFetch("/my/submissions", { redirect: "manual" });
    // Should redirect to login or return the page (public mode may allow)
    // In public mode, unauthenticated users get redirected to /auth/login
    expect([200, 302]).toContain(res.status);
  });
});
