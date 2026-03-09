import { describe, expect, test } from "bun:test";
import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import type { AppEnv, AppUser } from "../../src/types";
import { mockUser } from "../setup";

/**
 * Tests for auth guard helpers (requireAuth, requireRole, requireAuthOrRedirect).
 *
 * These test the guard functions in isolation by simulating the middleware
 * context, rather than testing the full auth middleware (which needs Supabase).
 */

// We can't easily mock the auth middleware's Supabase call, but we CAN test
// the guard helpers by importing them and calling with a mocked context.
// The guards just read c.get("user") — they don't call Supabase.

import { requireAuth, requireRole, requireAuthOrRedirect } from "../../src/middleware/auth";

function createAppWithGuard(
  user: AppUser | null,
  guard: "requireAuth" | "requireRole" | "requireAuthOrRedirect",
  role?: AppUser["role"],
) {
  const app = new Hono<AppEnv>();

  // Mock auth middleware — just sets the user
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });

  app.get("/test", (c) => {
    try {
      if (guard === "requireAuth") {
        const u = requireAuth(c);
        return c.json({ id: u.id });
      } else if (guard === "requireRole") {
        const u = requireRole(c, role!);
        return c.json({ id: u.id, role: u.role });
      } else {
        const result = requireAuthOrRedirect(c);
        if (result instanceof Response) return result;
        return c.json({ id: result.id });
      }
    } catch (err) {
      if (err instanceof HTTPException) {
        return c.json({ error: err.message }, err.status);
      }
      throw err;
    }
  });

  return app;
}

describe("requireAuth", () => {
  test("returns user when authenticated", async () => {
    const user = mockUser();
    const app = createAppWithGuard(user, "requireAuth");
    const res = await app.request("/test");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(user.id);
  });

  test("throws 401 when not authenticated", async () => {
    const app = createAppWithGuard(null, "requireAuth");
    const res = await app.request("/test");
    expect(res.status).toBe(401);
  });
});

describe("requireRole", () => {
  test("allows admin to access admin-only route", async () => {
    const admin = mockUser({ role: "admin" });
    const app = createAppWithGuard(admin, "requireRole", "admin");
    const res = await app.request("/test");
    expect(res.status).toBe(200);
  });

  test("allows admin to access curator route (higher role)", async () => {
    const admin = mockUser({ role: "admin" });
    const app = createAppWithGuard(admin, "requireRole", "curator");
    const res = await app.request("/test");
    expect(res.status).toBe(200);
  });

  test("allows curator to access curator route", async () => {
    const curator = mockUser({ role: "curator" });
    const app = createAppWithGuard(curator, "requireRole", "curator");
    const res = await app.request("/test");
    expect(res.status).toBe(200);
  });

  test("rejects user accessing curator route", async () => {
    const user = mockUser({ role: "user" });
    const app = createAppWithGuard(user, "requireRole", "curator");
    const res = await app.request("/test");
    expect(res.status).toBe(403);
  });

  test("rejects user accessing admin route", async () => {
    const user = mockUser({ role: "user" });
    const app = createAppWithGuard(user, "requireRole", "admin");
    const res = await app.request("/test");
    expect(res.status).toBe(403);
  });

  test("rejects unauthenticated user (401 before 403)", async () => {
    const app = createAppWithGuard(null, "requireRole", "admin");
    const res = await app.request("/test");
    expect(res.status).toBe(401);
  });
});

describe("requireAuthOrRedirect", () => {
  test("returns user when authenticated", async () => {
    const user = mockUser();
    const app = createAppWithGuard(user, "requireAuthOrRedirect");
    const res = await app.request("/test");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(user.id);
  });

  test("redirects to /auth/login when not authenticated", async () => {
    const app = createAppWithGuard(null, "requireAuthOrRedirect");
    const res = await app.request("/test", { redirect: "manual" });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/auth/login");
  });
});
