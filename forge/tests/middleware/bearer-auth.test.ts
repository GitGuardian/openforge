import { describe, expect, test, mock } from "bun:test";

// ---------------------------------------------------------------------------
// Mock state
// ---------------------------------------------------------------------------

let mockAuthUser: { id: string; email: string } | null = null;
let lastGetUserToken: string | null = null;

// ---------------------------------------------------------------------------
// Mock modules — must be before imports
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => ({
        where: () => ({
          limit: () =>
            Promise.resolve(
              mockAuthUser
                ? [
                    {
                      id: "user-001",
                      email: mockAuthUser.email,
                      displayName: "Test User",
                      role: "user",
                      authId: mockAuthUser.id,
                    },
                  ]
                : [],
            ),
        }),
      }),
    }),
    insert: () => ({
      values: () => ({
        returning: () =>
          Promise.resolve([
            {
              id: "user-new",
              email: mockAuthUser?.email ?? "",
              displayName: null,
              role: "user",
              authId: mockAuthUser?.id ?? "",
            },
          ]),
      }),
    }),
  },
}));

mock.module("../../src/lib/supabase", () => ({
  supabase: {
    auth: {
      getUser: (token: string) => {
        lastGetUserToken = token;
        if (mockAuthUser) {
          return Promise.resolve({
            data: { user: { id: mockAuthUser.id, email: mockAuthUser.email } },
            error: null,
          });
        }
        return Promise.resolve({
          data: { user: null },
          error: { message: "Invalid token" },
        });
      },
    },
  },
}));

// Import AFTER mocking
const { authMiddleware } = await import("../../src/middleware/auth");

import { Hono } from "hono";
import type { AppEnv } from "../../src/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createApp() {
  const app = new Hono<AppEnv>();
  app.use("*", authMiddleware);
  app.get("/test", (c) => {
    const user = c.get("user");
    if (!user) return c.json({ user: null });
    return c.json({ id: user.id, email: user.email });
  });
  return app;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("authMiddleware — Bearer token", () => {
  test("authenticates with valid Bearer token", async () => {
    mockAuthUser = { id: "auth-123", email: "bearer@example.com" };
    const app = createApp();
    const res = await app.request("/test", {
      headers: { Authorization: "Bearer valid-token-123" },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.email).toBe("bearer@example.com");
    expect(lastGetUserToken).toBe("valid-token-123");
  });

  test("rejects invalid Bearer token gracefully", async () => {
    mockAuthUser = null; // invalid token → no user
    const app = createApp();
    const res = await app.request("/test", {
      headers: { Authorization: "Bearer bad-token" },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.user).toBeNull();
  });

  test("falls back to cookie when no Authorization header", async () => {
    mockAuthUser = null;
    const app = createApp();
    const res = await app.request("/test");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.user).toBeNull();
  });

  test("ignores non-Bearer Authorization headers", async () => {
    mockAuthUser = null;
    const app = createApp();
    const res = await app.request("/test", {
      headers: { Authorization: "Basic dXNlcjpwYXNz" },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.user).toBeNull();
  });
});
