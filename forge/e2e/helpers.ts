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
    const envPath = resolve(__dirname, "../.env");
    const content = readFileSync(envPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) continue;
      env[trimmed.slice(0, eqIdx)] = trimmed.slice(eqIdx + 1);
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
