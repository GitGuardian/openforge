import { createMiddleware } from "hono/factory";
import { getCookie, deleteCookie } from "hono/cookie";
import { HTTPException } from "hono/http-exception";
import { eq } from "drizzle-orm";
import { db } from "../db";
import { users } from "../db/schema";
import type { AppEnv, AppUser } from "../types";
import { supabase } from "../lib/supabase";
import type { Context } from "hono";

// ---------------------------------------------------------------------------
// Helpers — look up or create an app-level user from a Supabase auth user
// ---------------------------------------------------------------------------

async function getOrCreateUser(authId: string, email: string): Promise<AppUser> {
  // Try to find existing user by auth_id
  const existing = await db
    .select()
    .from(users)
    .where(eq(users.authId, authId))
    .limit(1);

  if (existing.length > 0) {
    const row = existing[0];
    return {
      id: row.id,
      email: row.email,
      displayName: row.displayName,
      role: row.role as AppUser["role"],
      authId: row.authId ?? authId,
    };
  }

  // Create new user
  const inserted = await db
    .insert(users)
    .values({
      email,
      role: "user",
      authId,
    })
    .returning();

  const row = inserted[0];
  return {
    id: row.id,
    email: row.email,
    displayName: row.displayName,
    role: row.role as AppUser["role"],
    authId: row.authId ?? authId,
  };
}

// ---------------------------------------------------------------------------
// Auth middleware — reads token from cookies, validates via Supabase Auth,
// and sets the AppUser (or null) on the Hono context.
// ---------------------------------------------------------------------------

export const authMiddleware = createMiddleware<AppEnv>(async (c, next) => {
  const accessToken = getCookie(c, "sb-access-token");

  if (!accessToken) {
    c.set("user", null);

    // In private mode, non-auth routes must redirect to login
    if (isPrivateMode() && !isAuthRoute(c.req.path)) {
      return c.redirect("/auth/login");
    }

    await next();
    return;
  }

  // Validate the token with Supabase Auth
  const {
    data: { user: authUser },
    error,
  } = await supabase.auth.getUser(accessToken);

  if (error || !authUser) {
    // Token is invalid or expired — clear cookies
    deleteCookie(c, "sb-access-token", { path: "/" });
    deleteCookie(c, "sb-refresh-token", { path: "/" });
    c.set("user", null);

    if (isPrivateMode() && !isAuthRoute(c.req.path)) {
      return c.redirect("/auth/login");
    }

    await next();
    return;
  }

  // Look up (or create) the app-level user
  const appUser = await getOrCreateUser(authUser.id, authUser.email ?? "");
  c.set("user", appUser);

  await next();
});

// ---------------------------------------------------------------------------
// Guard helpers — use in route handlers to enforce auth requirements
// ---------------------------------------------------------------------------

/**
 * Throws 401 if no user is authenticated. Returns the AppUser otherwise.
 * Use in API routes that require authentication.
 */
export function requireAuth(c: Context<AppEnv>): AppUser {
  const user = c.get("user");
  if (!user) {
    throw new HTTPException(401, { message: "Authentication required" });
  }
  return user;
}

/**
 * Throws 403 if the authenticated user does not have the required role.
 * Implicitly requires authentication (throws 401 if not logged in).
 */
export function requireRole(c: Context<AppEnv>, role: AppUser["role"]): AppUser {
  const user = requireAuth(c);

  const hierarchy: Record<AppUser["role"], number> = {
    user: 0,
    curator: 1,
    admin: 2,
  };

  if (hierarchy[user.role] < hierarchy[role]) {
    throw new HTTPException(403, {
      message: `Role "${role}" required. You have "${user.role}".`,
    });
  }

  return user;
}

/**
 * For page routes — redirects to /auth/login instead of throwing 401.
 * Returns the AppUser if authenticated.
 */
export function requireAuthOrRedirect(c: Context<AppEnv>): AppUser | Response {
  const user = c.get("user");
  if (!user) {
    return c.redirect("/auth/login");
  }
  return user;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function isPrivateMode(): boolean {
  return process.env.OPENFORGE_MODE === "private";
}

function isAuthRoute(path: string): boolean {
  return path.startsWith("/auth/") || path === "/auth" || path === "/health";
}
