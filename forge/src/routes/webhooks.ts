import { Hono } from "hono";
import { timingSafeEqual } from "crypto";
import { eq } from "drizzle-orm";
import { db } from "../db";
import { registries } from "../db/schema";
import { indexRegistry } from "../lib/indexer";
import type { AppEnv } from "../types";

export const webhookRoutes = new Hono<AppEnv>();

// ---------------------------------------------------------------------------
// HMAC-SHA256 signature verification (timing-safe)
// ---------------------------------------------------------------------------

function verifySignature(secret: string, payload: string, signature: string): boolean {
  const hmac = new Bun.CryptoHasher("sha256", secret);
  hmac.update(payload);
  const expectedSig = `sha256=${hmac.digest("hex")}`;

  if (signature.length !== expectedSig.length) return false;
  return timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSig),
  );
}

// ---------------------------------------------------------------------------
// POST /api/webhooks/github
// ---------------------------------------------------------------------------

webhookRoutes.post("/api/webhooks/github", async (c) => {
  const event = c.req.header("X-GitHub-Event");
  if (event !== "push") {
    return c.json({ message: "ignored event" }, 200);
  }

  const rawBody = await c.req.text();
  const signature = c.req.header("X-Hub-Signature-256");
  if (!signature) {
    return c.json({ error: "missing signature" }, 401);
  }

  // Parse payload to find repo URL
  let payload: { repository?: { clone_url?: string; html_url?: string }; ref?: string };
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return c.json({ error: "invalid JSON" }, 400);
  }

  // Only process pushes to branches (ignore tags)
  const ref = payload.ref;
  if (!ref?.startsWith("refs/heads/")) {
    return c.json({ message: "ignored non-branch ref" }, 200);
  }

  const repoUrl = payload.repository?.clone_url || payload.repository?.html_url;
  if (!repoUrl) {
    return c.json({ error: "no repository URL in payload" }, 400);
  }

  // Find matching registry by URL
  const allRegistries = await db.select().from(registries);
  const registry = allRegistries.find(
    (r) =>
      repoUrl.includes(r.gitUrl.replace(/\.git$/, "")) ||
      r.gitUrl.includes(repoUrl.replace(/\.git$/, "")),
  );
  if (!registry) {
    return c.json({ error: "no matching registry" }, 404);
  }

  // Verify HMAC signature
  if (!registry.webhookSecret) {
    return c.json({ error: "registry has no webhook secret configured" }, 403);
  }
  if (!verifySignature(registry.webhookSecret, rawBody, signature)) {
    return c.json({ error: "invalid signature" }, 401);
  }

  // Concurrency guard: skip if indexed less than 60s ago
  if (registry.indexedAt) {
    const elapsed = Date.now() - new Date(registry.indexedAt).getTime();
    if (elapsed < 60_000) {
      return c.json({ message: "indexing already in progress" }, 200);
    }
  }

  // Mark as indexing now (before async work)
  await db
    .update(registries)
    .set({ indexedAt: new Date() })
    .where(eq(registries.id, registry.id));

  // Run indexing in background — don't block the webhook response
  indexRegistry(registry.id)
    .then((result) => {
      console.log(`Webhook indexing complete for ${registry.name}:`, result);
    })
    .catch((err) => {
      console.error(`Webhook indexing failed for ${registry.name}:`, err);
    });

  return c.json({ message: "indexing started" }, 200);
});
