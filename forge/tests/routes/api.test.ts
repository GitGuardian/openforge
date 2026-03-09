import { describe, expect, test, mock, beforeEach } from "bun:test";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockPluginRows = [
  {
    id: "plugin-001",
    name: "my-cool-plugin",
    description: "A cool plugin",
    category: "productivity",
    tags: ["ai", "code"],
    version: "1.0.0",
    installCount: 42,
    gitPath: ".claude-plugin",
    gitSha: "abc123",
    status: "approved",
    gitUrl: "https://github.com/acme/cool-repo.git",
  },
];

const mockSkillRows = [
  {
    skillName: "code-review",
    skillDescription: "Reviews code for quality",
    skillMdPath: "skills/code-review/SKILL.md",
    pluginCategory: "development",
    pluginTags: ["review"],
    pluginVersion: "2.0.0",
    pluginInstallCount: 100,
    pluginGitSha: "def456",
    pluginStatus: "approved",
    gitUrl: "https://github.com/acme/skills-repo",
  },
];

let lastInsertedEvent: Record<string, unknown> | null = null;
let lastUpdatedPlugin: string | null = null;

// ---------------------------------------------------------------------------
// Mock db module
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    select: (fields: unknown) => ({
      from: (table: unknown) => ({
        innerJoin: (...args: unknown[]) => ({
          where: () => Promise.resolve(mockPluginRows),
          leftJoin: () => ({
            where: () => Promise.resolve(mockSkillRows),
          }),
        }),
      }),
    }),
    insert: (table: unknown) => ({
      values: (values: Record<string, unknown>) => {
        lastInsertedEvent = values;
        return Promise.resolve();
      },
    }),
    update: (table: unknown) => ({
      set: (values: unknown) => ({
        where: (condition: unknown) => {
          // Extract plugin name from the condition for tracking
          lastUpdatedPlugin = "updated";
          return Promise.resolve();
        },
      }),
    }),
  },
}));

// Mock supabase (auth middleware dependency, not used in API routes directly)
mock.module("../../src/lib/supabase", () => ({
  supabase: { auth: { getUser: () => Promise.resolve({ data: { user: null }, error: null }) } },
}));

const { apiRoutes } = await import("../../src/routes/api");

// Wrap with mock auth middleware for testing
import { Hono } from "hono";
import type { AppEnv } from "../../src/types";

function createApiApp() {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", null);
    await next();
  });
  app.route("/", apiRoutes);
  return app;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GET /api/marketplace.json", () => {
  test("returns 200 with packages array", async () => {
    const app = createApiApp();
    const res = await app.request("/api/marketplace.json");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.version).toBe("0.1.0");
    expect(body.packages).toBeArray();
    expect(body.packages).toHaveLength(1);
  });

  test("includes correct package fields", async () => {
    const app = createApiApp();
    const res = await app.request("/api/marketplace.json");
    const body = await res.json();
    const pkg = body.packages[0];

    expect(pkg.id).toBe("plugin-001");
    expect(pkg.name).toBe("my-cool-plugin");
    expect(pkg.displayName).toBe("My Cool Plugin");
    expect(pkg.description).toBe("A cool plugin");
    expect(pkg.category).toBe("productivity");
    expect(pkg.tags).toEqual(["ai", "code"]);
    expect(pkg.version).toBe("1.0.0");
    expect(pkg.installCount).toBe(42);
    expect(pkg.author).toBe("acme");
    expect(pkg.gitSha).toBe("abc123");
  });

  test("sets Cache-Control header", async () => {
    const app = createApiApp();
    const res = await app.request("/api/marketplace.json");
    expect(res.headers.get("Cache-Control")).toBe("public, max-age=300");
  });
});

describe("GET /.well-known/skills/index.json", () => {
  test("returns 200 with skills array", async () => {
    const app = createApiApp();
    const res = await app.request("/.well-known/skills/index.json");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.version).toBe("1.0.0");
    expect(body.skills).toBeArray();
    expect(body.skills).toHaveLength(1);
  });

  test("includes correct skill fields", async () => {
    const app = createApiApp();
    const res = await app.request("/.well-known/skills/index.json");
    const body = await res.json();
    const skill = body.skills[0];

    expect(skill.name).toBe("code-review");
    expect(skill.displayName).toBe("Code Review");
    expect(skill.description).toBe("Reviews code for quality");
    expect(skill.category).toBe("development");
    expect(skill.author).toBe("acme");
    expect(skill.source.type).toBe("git");
    expect(skill.source.path).toBe("skills/code-review/SKILL.md");
  });

  test("sets Cache-Control header", async () => {
    const app = createApiApp();
    const res = await app.request("/.well-known/skills/index.json");
    expect(res.headers.get("Cache-Control")).toBe("public, max-age=300");
  });

  test("only includes skills from approved plugins", async () => {
    const app = createApiApp();
    const res = await app.request("/.well-known/skills/index.json");
    expect(res.status).toBe(200);
    const body = await res.json();
    // All returned skills come from approved plugins (mock only has approved)
    expect(body.skills).toHaveLength(1);
    expect(body.skills[0].name).toBe("code-review");
  });
});

describe("POST /api/telemetry", () => {
  beforeEach(() => {
    lastInsertedEvent = null;
    lastUpdatedPlugin = null;
  });

  test("accepts valid telemetry event", async () => {
    const app = createApiApp();
    const res = await app.request("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plugin_name: "my-plugin",
        source: "cli",
      }),
    });
    expect(res.status).toBe(204);
  });

  test("rejects missing plugin_name", async () => {
    const app = createApiApp();
    const res = await app.request("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "cli" }),
    });
    expect(res.status).toBe(400);
  });

  test("rejects invalid source", async () => {
    const app = createApiApp();
    const res = await app.request("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plugin_name: "my-plugin",
        source: "invalid-source",
      }),
    });
    expect(res.status).toBe(400);
  });

  test("rejects plugin_name with path traversal", async () => {
    const app = createApiApp();
    const res = await app.request("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plugin_name: "../etc/passwd",
        source: "cli",
      }),
    });
    expect(res.status).toBe(400);
  });

  test("rejects oversized content-length", async () => {
    const app = createApiApp();
    const res = await app.request("/api/telemetry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": "10000",
      },
      body: JSON.stringify({
        plugin_name: "my-plugin",
        source: "cli",
      }),
    });
    expect(res.status).toBe(413);
  });

  test("accepts all valid sources", async () => {
    const app = createApiApp();
    for (const source of ["cli", "hook-activate", "marketplace-fetch"]) {
      const res = await app.request("/api/telemetry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plugin_name: "test-plugin",
          source,
        }),
      });
      expect(res.status).toBe(204);
    }
  });

  test("rejects agents array with too many items", async () => {
    const app = createApiApp();
    const agents = Array.from({ length: 21 }, (_, i) => `agent-${i}`);
    const res = await app.request("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plugin_name: "my-plugin",
        source: "cli",
        agents,
      }),
    });
    expect(res.status).toBe(400);
  });

  test("rejects plugin_name exceeding 200 chars", async () => {
    const app = createApiApp();
    const res = await app.request("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plugin_name: "x".repeat(201),
        source: "cli",
      }),
    });
    expect(res.status).toBe(400);
  });
});
