import { Hono } from "hono";
import { eq, or, isNull, sql } from "drizzle-orm";
import { db } from "../db";
import { plugins, skills, registries, installEvents } from "../db/schema";
import type { AppEnv } from "../types";

export const apiRoutes = new Hono<AppEnv>();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Extract the owner (org or user) from a GitHub-style git URL.
 * Supports:
 *   https://github.com/OWNER/repo.git
 *   https://github.com/OWNER/repo
 *   git@github.com:OWNER/repo.git
 */
function extractAuthor(gitUrl: string): string {
  try {
    // HTTPS URL
    const httpsMatch = gitUrl.match(
      /https?:\/\/[^/]+\/([^/]+)\/[^/]+/,
    );
    if (httpsMatch) return httpsMatch[1];

    // SSH URL (git@host:owner/repo)
    const sshMatch = gitUrl.match(/:([^/]+)\/[^/]+/);
    if (sshMatch) return sshMatch[1];
  } catch {
    // fall through
  }
  return "unknown";
}

/**
 * Derive a display name from a plugin name.
 * "my-cool-plugin" → "My Cool Plugin"
 */
function toDisplayName(name: string): string {
  return name
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const VALID_SOURCES = new Set(["cli", "hook-activate", "marketplace-fetch"]);

const PATH_TRAVERSAL_RE = /[/\\]|\.\./;

// ---------------------------------------------------------------------------
// GET /api/marketplace.json
// ---------------------------------------------------------------------------

apiRoutes.get("/api/marketplace.json", async (c) => {
  const rows = await db
    .select({
      id: plugins.id,
      name: plugins.name,
      description: plugins.description,
      category: plugins.category,
      tags: plugins.tags,
      version: plugins.version,
      installCount: plugins.installCount,
      gitPath: plugins.gitPath,
      gitSha: plugins.gitSha,
      status: plugins.status,
      gitUrl: registries.gitUrl,
    })
    .from(plugins)
    .innerJoin(registries, eq(plugins.registryId, registries.id))
    .where(eq(plugins.status, "approved"));

  const packages = rows.map((row) => ({
    id: row.id,
    name: row.name,
    description: row.description,
    displayName: toDisplayName(row.name),
    category: row.category,
    tags: row.tags,
    version: row.version,
    installCount: row.installCount,
    author: extractAuthor(row.gitUrl),
    downloadUrl: row.gitUrl,
    gitPath: row.gitPath,
    gitSha: row.gitSha,
    status: row.status,
  }));

  c.header("Cache-Control", "public, max-age=300");
  return c.json({ version: "0.1.0", packages });
});

// ---------------------------------------------------------------------------
// GET /.well-known/skills/index.json
// ---------------------------------------------------------------------------

apiRoutes.get("/.well-known/skills/index.json", async (c) => {
  const rows = await db
    .select({
      // skill fields
      skillName: skills.name,
      skillDescription: skills.description,
      skillMdPath: skills.skillMdPath,
      // plugin fields (may be null if standalone skill)
      pluginCategory: plugins.category,
      pluginTags: plugins.tags,
      pluginVersion: plugins.version,
      pluginInstallCount: plugins.installCount,
      pluginGitSha: plugins.gitSha,
      // registry fields
      gitUrl: registries.gitUrl,
    })
    .from(skills)
    .innerJoin(registries, eq(skills.registryId, registries.id))
    .leftJoin(plugins, eq(skills.pluginId, plugins.id))
    .where(or(eq(plugins.status, "approved"), isNull(plugins.id)));

  const skillsList = rows.map((row) => ({
    name: row.skillName,
    displayName: toDisplayName(row.skillName),
    description: row.skillDescription ?? "",
    category: row.pluginCategory ?? "uncategorized",
    tags: row.pluginTags ?? [],
    author: extractAuthor(row.gitUrl),
    version: row.pluginVersion ?? "1.0.0",
    source: {
      type: "git" as const,
      url: row.gitUrl,
      path: row.skillMdPath,
      sha: row.pluginGitSha ?? "",
    },
    metadata: {
      installCount: row.pluginInstallCount ?? 0,
    },
  }));

  c.header("Cache-Control", "public, max-age=300");
  return c.json({ version: "1.0.0", skills: skillsList });
});

// ---------------------------------------------------------------------------
// POST /api/telemetry
// ---------------------------------------------------------------------------

apiRoutes.post("/api/telemetry", async (c) => {
  try {
    // Body size limit check
    const contentLength = c.req.header("content-length");
    if (contentLength && parseInt(contentLength, 10) > 4096) {
      return c.body(null, 413);
    }

    const body = await c.req.json();

    // Validate plugin_name (required, string, max 200 chars, no path traversal)
    if (
      typeof body.plugin_name !== "string" ||
      body.plugin_name.length === 0 ||
      body.plugin_name.length > 200
    ) {
      return c.json({ error: "Invalid plugin_name" }, 400);
    }
    if (PATH_TRAVERSAL_RE.test(body.plugin_name)) {
      return c.json({ error: "Invalid plugin_name" }, 400);
    }

    // Validate source (required, must be known value)
    if (typeof body.source !== "string" || !VALID_SOURCES.has(body.source)) {
      return c.json({ error: "Invalid source" }, 400);
    }

    // Validate agents (optional, array of strings, max 20 items)
    let agents: string[] = [];
    if (body.agents !== undefined) {
      if (
        !Array.isArray(body.agents) ||
        body.agents.length > 20 ||
        !body.agents.every((a: unknown) => typeof a === "string")
      ) {
        return c.json({ error: "Invalid agents" }, 400);
      }
      agents = body.agents as string[];
    }

    // Insert into install_events
    await db.insert(installEvents).values({
      pluginName: body.plugin_name,
      skillName: typeof body.skill_name === "string" ? body.skill_name : null,
      version: typeof body.version === "string" ? body.version : null,
      source: body.source,
      agents,
      cliVersion:
        typeof body.cli_version === "string" ? body.cli_version : null,
      isCi: typeof body.is_ci === "boolean" ? body.is_ci : false,
    });

    // Best-effort increment of plugins.install_count
    try {
      await db
        .update(plugins)
        .set({ installCount: sql`${plugins.installCount} + 1` })
        .where(eq(plugins.name, body.plugin_name));
    } catch {
      // Best-effort — don't fail the request if the plugin doesn't exist
    }

    return c.body(null, 204);
  } catch (err) {
    console.error("Telemetry error:", err);
    return c.json({ error: "Bad request" }, 400);
  }
});
