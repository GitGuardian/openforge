/**
 * Test helpers for The Forge.
 *
 * Provides utilities to create testable Hono apps with mocked auth context,
 * without needing a running server or real database connections.
 */

import { Hono } from "hono";
import type { AppEnv, AppUser } from "../src/types";

/**
 * Create a mock AppUser for testing.
 */
export function mockUser(overrides: Partial<AppUser> = {}): AppUser {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    email: "test@example.com",
    displayName: "Test User",
    role: "user",
    authId: "auth-00000000-0000-0000-0000-000000000001",
    ...overrides,
  };
}

/**
 * Create a Hono app with auth context pre-set (bypasses real auth middleware).
 * Pass `user: null` for unauthenticated requests.
 */
export function createTestApp(user: AppUser | null = null): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });
  return app;
}

/**
 * Shorthand to make a request to a Hono app and return the response.
 */
export async function request(
  app: Hono<AppEnv>,
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return app.request(path, init);
}
