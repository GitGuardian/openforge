/**
 * Integration test helpers for The Forge.
 *
 * These helpers make real HTTP requests against a running Forge server
 * and real Supabase instance. Requires:
 *   - Local Supabase running (supabase start)
 *   - Forge server running (bun run dev)
 *
 * Environment variables (auto-detected from forge/.env if not set):
 *   FORGE_URL          — Forge server URL (default: http://localhost:3000)
 *   SUPABASE_URL       — Supabase API URL (default: http://127.0.0.1:54321)
 *   SUPABASE_ANON_KEY  — Supabase anon key
 *   SUPABASE_SERVICE_ROLE_KEY — Supabase service role key (for user cleanup)
 */

// ---------------------------------------------------------------------------
// Load env from forge/.env if variables aren't already set
// ---------------------------------------------------------------------------

import { resolve } from "path";
import { readFileSync } from "fs";

function loadEnvIfNeeded(): void {
  if (process.env.SUPABASE_ANON_KEY) return; // already set

  try {
    const envPath = resolve(import.meta.dir, "../../.env");
    const content = readFileSync(envPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) continue;
      const key = trimmed.slice(0, eqIdx);
      const value = trimmed.slice(eqIdx + 1);
      if (!process.env[key]) {
        process.env[key] = value;
      }
    }
  } catch {
    // .env not found — rely on environment variables
  }
}

loadEnvIfNeeded();

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export const BASE_URL = process.env.FORGE_URL || "http://localhost:3000";
export const SUPABASE_URL =
  process.env.SUPABASE_URL || "http://127.0.0.1:54321";
export const ANON_KEY = process.env.SUPABASE_ANON_KEY || "";

/** Create a test user via Supabase Auth API and return access token + user info */
export async function createTestUser(
  email?: string,
  password?: string,
): Promise<{ accessToken: string; email: string; userId: string }> {
  const testEmail =
    email ||
    `test-${Date.now()}-${Math.random().toString(36).slice(2)}@test.local`;
  const testPassword = password || "test-password-123!";

  const signupRes = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: ANON_KEY,
    },
    body: JSON.stringify({ email: testEmail, password: testPassword }),
  });

  if (!signupRes.ok) {
    const err = await signupRes.text();
    throw new Error(`Failed to create test user: ${signupRes.status} ${err}`);
  }

  const data = await signupRes.json();

  // Local Supabase has email confirmations disabled — tokens returned immediately
  return {
    accessToken: data.access_token,
    email: testEmail,
    userId: data.user?.id || data.id,
  };
}

/** Make an authenticated request to the Forge server */
export async function authFetch(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${token}`,
    },
  });
}

/** Make an unauthenticated request to the Forge server */
export async function anonFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(`${BASE_URL}${path}`, init);
}

/** Clean up a test user — delete from Supabase Auth via service role key */
export async function deleteTestUser(userId: string): Promise<void> {
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!serviceRoleKey) return; // skip cleanup if no service role key

  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    method: "DELETE",
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
    },
  });
}
