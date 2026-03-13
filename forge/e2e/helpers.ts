/**
 * Shared helpers for Playwright E2E tests.
 * Reads env vars or falls back to local Supabase defaults.
 */

import { resolve } from "path";
import { readFileSync } from "fs";
import type { APIRequestContext } from "@playwright/test";

// Load from .env if env vars aren't set
function loadEnv(): Record<string, string> {
  const env: Record<string, string> = {};
  try {
    // Try multiple paths — __dirname may not be set in ESM context
    const candidates = [
      typeof __dirname !== "undefined" ? resolve(__dirname, "../.env") : null,
      resolve(process.cwd(), ".env"),
      resolve(process.cwd(), "forge/.env"),
    ].filter(Boolean) as string[];

    for (const envPath of candidates) {
      try {
        const content = readFileSync(envPath, "utf-8");
        for (const line of content.split("\n")) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith("#")) continue;
          const eqIdx = trimmed.indexOf("=");
          if (eqIdx === -1) continue;
          env[trimmed.slice(0, eqIdx)] = trimmed.slice(eqIdx + 1);
        }
        break; // Found and parsed successfully
      } catch {
        continue;
      }
    }
  } catch {
    // .env not found
  }
  return env;
}

const dotenv = loadEnv();

export const SUPABASE_URL =
  process.env.SUPABASE_URL || dotenv.SUPABASE_URL || "http://127.0.0.1:54321";
export const ANON_KEY =
  process.env.SUPABASE_ANON_KEY || dotenv.SUPABASE_ANON_KEY || "";
export const SERVICE_ROLE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY || dotenv.SUPABASE_SERVICE_ROLE_KEY || "";

/** Create a test user via Supabase Auth API and return credentials */
export async function createE2EUser(request: APIRequestContext) {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2)}@test.local`;
  const password = "test-password-123!";

  const res = await request.post(`${SUPABASE_URL}/auth/v1/signup`, {
    data: { email, password },
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
  });

  if (!res.ok()) {
    throw new Error(`Failed to create E2E user: ${res.status()} ${await res.text()}`);
  }

  return { email, password };
}

/** Sign in via Supabase Auth API and return userId + access token */
export async function signInAndGetToken(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<{ userId: string; token: string }> {
  const res = await request.post(
    `${SUPABASE_URL}/auth/v1/token?grant_type=password`,
    {
      data: { email, password },
      headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    },
  );
  if (!res.ok()) throw new Error(`Sign-in failed: ${res.status()}`);
  const data = await res.json();
  return { userId: data.user?.id as string, token: data.access_token as string };
}

/** Promote a user to curator role via Supabase REST API (service role key) */
export async function promoteUserToCurator(
  request: APIRequestContext,
  userId: string,
): Promise<void> {
  if (!SERVICE_ROLE_KEY) {
    throw new Error("SUPABASE_SERVICE_ROLE_KEY not set — check forge/.env");
  }
  // userId is the Supabase Auth ID; the users table links via auth_id column
  const res = await request.patch(
    `${SUPABASE_URL}/rest/v1/users?auth_id=eq.${userId}`,
    {
      data: { role: "curator" },
      headers: {
        apikey: SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
    },
  );
  if (!res.ok()) {
    throw new Error(
      `Failed to promote to curator: ${res.status()} ${await res.text()}`,
    );
  }
}

/** Create a pending submission via the Forge API */
export async function createTestSubmission(
  request: APIRequestContext,
  token: string,
  forgeUrl: string = "http://localhost:3000",
): Promise<{ id: string; gitUrl: string }> {
  const gitUrl = `https://github.com/e2e-curator-test/plugin-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const res = await request.post(`${forgeUrl}/api/submissions`, {
    data: { gitUrl, description: "Curator E2E test submission" },
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to create test submission: ${res.status()} ${await res.text()}`,
    );
  }
  const data = await res.json();
  return { id: data.id, gitUrl };
}

/** Reset server-side rate limits (requires NODE_ENV=test on the Forge server) */
export async function resetRateLimits(
  request: APIRequestContext,
  forgeUrl: string = "http://localhost:3000",
): Promise<void> {
  await request.post(`${forgeUrl}/_test/reset-rate-limits`);
}

/** Login a user via the browser UI */
export async function loginViaUI(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
) {
  await page.goto("/auth/login");
  await page.fill("input[name='email']", email);
  await page.fill("input[name='password']", password);
  await page.click("button[type='submit']");
  await page.waitForURL(
    (url) => !url.pathname.includes("/auth/login"),
    { timeout: 10_000 },
  );
}
