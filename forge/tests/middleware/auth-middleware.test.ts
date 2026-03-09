import { describe, expect, test, mock, beforeEach, afterEach } from "bun:test";
import { Hono } from "hono";
import type { AppEnv } from "../../src/types";

// ---------------------------------------------------------------------------
// Configurable mock state
// ---------------------------------------------------------------------------

let mockSupabaseUser: { id: string; email: string } | null = null;
let mockSupabaseError: { message: string } | null = null;
let mockDbUser: {
  id: string;
  email: string;
  displayName: string | null;
  role: string;
  authId: string;
} | null = null;
let insertedUser: Record<string, unknown> | null = null;

// ---------------------------------------------------------------------------
// Mock modules — must be set up before importing auth middleware
// ---------------------------------------------------------------------------

mock.module("../../src/lib/supabase", () => ({
  supabase: {
    auth: {
      getUser: async (token: string) => {
        if (mockSupabaseError) {
          return { data: { user: null }, error: mockSupabaseError };
        }
        return {
          data: { user: mockSupabaseUser },
          error: null,
        };
      },
    },
  },
  supabaseAdmin: null,
}));

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => ({
        where: () => ({
          limit: () => Promise.resolve(mockDbUser ? [mockDbUser] : []),
        }),
      }),
    }),
    insert: () => ({
      values: (values: Record<string, unknown>) => ({
        returning: () => {
          insertedUser = values;
          return Promise.resolve([{
            id: "new-user-id",
            email: values.email,
            displayName: null,
            role: values.role ?? "user",
            authId: values.authId,
          }]);
        },
      }),
    }),
  },
}));

// Import AFTER mocking
const { authMiddleware } = await import("../../src/middleware/auth");

// ---------------------------------------------------------------------------
// Helper: create a test app with the real auth middleware
// ---------------------------------------------------------------------------

function createAuthApp(): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  app.use("*", authMiddleware);
  app.get("/test", (c) => {
    const user = c.get("user");
    return c.json({ user });
  });
  app.get("/health", (c) => c.json({ ok: true }));
  app.get("/auth/login", (c) => c.text("login page"));
  return app;
}

function requestWithCookie(
  app: Hono<AppEnv>,
  path: string,
  accessToken?: string,
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Cookie"] = `sb-access-token=${accessToken}`;
  }
  return app.request(path, { headers, redirect: "manual" }) as Promise<Response>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("authMiddleware", () => {
  const originalMode = process.env.OPENFORGE_MODE;

  beforeEach(() => {
    mockSupabaseUser = null;
    mockSupabaseError = null;
    mockDbUser = null;
    insertedUser = null;
    delete process.env.OPENFORGE_MODE;
  });

  afterEach(() => {
    if (originalMode !== undefined) {
      process.env.OPENFORGE_MODE = originalMode;
    } else {
      delete process.env.OPENFORGE_MODE;
    }
  });

  // --- No token ---

  test("sets user to null when no access token cookie", async () => {
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.user).toBeNull();
  });

  test("proceeds to route handler when no token (public mode)", async () => {
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test");
    expect(res.status).toBe(200);
  });

  // --- Private mode ---

  test("redirects to /auth/login in private mode when no token", async () => {
    process.env.OPENFORGE_MODE = "private";
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test");
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/auth/login");
  });

  test("allows /auth/ routes in private mode without token", async () => {
    process.env.OPENFORGE_MODE = "private";
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/auth/login");
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toBe("login page");
  });

  test("allows /health in private mode without token", async () => {
    process.env.OPENFORGE_MODE = "private";
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/health");
    expect(res.status).toBe(200);
  });

  // --- Valid token, existing user ---

  test("sets user from DB when token is valid and user exists", async () => {
    mockSupabaseUser = { id: "auth-123", email: "alice@example.com" };
    mockDbUser = {
      id: "user-001",
      email: "alice@example.com",
      displayName: "Alice",
      role: "admin",
      authId: "auth-123",
    };
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test", "valid-token");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.user).not.toBeNull();
    expect(body.user.id).toBe("user-001");
    expect(body.user.email).toBe("alice@example.com");
    expect(body.user.role).toBe("admin");
    expect(body.user.displayName).toBe("Alice");
  });

  // --- Valid token, new user (auto-create) ---

  test("creates new user when token is valid but user not in DB", async () => {
    mockSupabaseUser = { id: "auth-new", email: "newbie@example.com" };
    mockDbUser = null; // not in DB
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test", "valid-token");
    expect(res.status).toBe(200);
    expect(insertedUser).not.toBeNull();
    expect(insertedUser!.email).toBe("newbie@example.com");
    expect(insertedUser!.authId).toBe("auth-new");
    expect(insertedUser!.role).toBe("user");

    const body = await res.json();
    expect(body.user).not.toBeNull();
    expect(body.user.email).toBe("newbie@example.com");
  });

  // --- Invalid/expired token ---

  test("sets user to null when Supabase returns error", async () => {
    mockSupabaseError = { message: "Invalid JWT" };
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test", "expired-token");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.user).toBeNull();
  });

  test("clears cookies on invalid token (Set-Cookie header)", async () => {
    mockSupabaseError = { message: "Invalid JWT" };
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test", "expired-token");
    // Check that cookies are cleared (deleteCookie sets max-age=0)
    const setCookies = res.headers.getAll("Set-Cookie");
    const accessClear = setCookies.some(
      (c: string) => c.includes("sb-access-token") && c.includes("Max-Age=0"),
    );
    const refreshClear = setCookies.some(
      (c: string) => c.includes("sb-refresh-token") && c.includes("Max-Age=0"),
    );
    expect(accessClear).toBe(true);
    expect(refreshClear).toBe(true);
  });

  test("redirects to login in private mode when token is invalid", async () => {
    process.env.OPENFORGE_MODE = "private";
    mockSupabaseError = { message: "Token expired" };
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test", "expired-token");
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/auth/login");
  });

  // --- Supabase returns no user (no error but user is null) ---

  test("sets user to null when Supabase returns no user and no error", async () => {
    mockSupabaseUser = null;
    mockSupabaseError = null;
    const app = createAuthApp();
    const res = await requestWithCookie(app, "/test", "weird-token");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.user).toBeNull();
  });
});
