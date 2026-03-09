import { describe, expect, test, mock, beforeEach } from "bun:test";
import { Hono } from "hono";
import type { AppEnv, AppUser } from "../../src/types";
import { mockUser } from "../setup";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_PLUGIN = {
  id: "plugin-001",
  registryId: "reg-001",
  name: "test-plugin",
  version: "1.0.0",
  description: "A test plugin",
  category: "productivity",
  tags: ["ai", "test"],
  readmeHtml: "<p>Hello</p>",
  pluginJson: {},
  gitPath: "owner/repo",
  gitSha: "abc123def456",
  status: "approved",
  installCount: 42,
  voteScore: 10,
  createdAt: new Date(),
  updatedAt: new Date(),
  userVote: 0,
};

let mockPluginRows: typeof MOCK_PLUGIN[] = [MOCK_PLUGIN];
let mockTotalCount = 1;
let mockDetailPlugin: typeof MOCK_PLUGIN | null = MOCK_PLUGIN;
let mockSkills: Array<{ id: string; name: string; description: string | null }> = [];
let mockUserVoteRows: Array<{ value: number }> = [];
let mockCommentRows: unknown[] = [];

// ---------------------------------------------------------------------------
// Mock modules
// ---------------------------------------------------------------------------

// Complex DB mock supporting the multiple query patterns in pages.ts
mock.module("../../src/db", () => {
  const makeSelectResult = (fields?: unknown) => {
    // Vote value select: db.select({ value: votes.value }).from(votes).where().limit()
    if (fields && typeof fields === "object" && "value" in fields && !("total" in fields)) {
      return {
        from: () => ({
          where: () => ({
            limit: () => Promise.resolve(mockUserVoteRows),
          }),
        }),
      };
    }
    // Count select: db.select({ total: count() }).from(plugins).where()
    if (fields && typeof fields === "object" && "total" in fields) {
      return {
        from: () => ({
          where: () => Promise.resolve([{ total: mockTotalCount }]),
        }),
      };
    }
    // Regular select (plugins, skills, comments, etc.)
    return {
      from: () => ({
        // Plugin detail: .where().limit()
        where: (cond: unknown) => ({
          limit: (n: number) => Promise.resolve(mockDetailPlugin ? [mockDetailPlugin] : []),
          orderBy: (sort: unknown) => ({
            limit: (n: number) => ({
              offset: (o: number) => Promise.resolve(mockPluginRows),
            }),
          }),
        }),
        // Catalogue with user votes: .leftJoin().where().orderBy().limit().offset()
        leftJoin: (table: unknown, cond: unknown) => ({
          where: (w: unknown) => ({
            orderBy: (sort: unknown) => ({
              limit: (n: number) => ({
                offset: (o: number) => Promise.resolve(mockPluginRows),
              }),
            }),
          }),
        }),
        // Comments: .innerJoin().where()
        innerJoin: (table: unknown, cond: unknown) => ({
          where: () => Promise.resolve(mockCommentRows),
        }),
      }),
    };
  };
  return { db: { select: makeSelectResult } };
});

// Mock supabase (imported by auth)
mock.module("../../src/lib/supabase", () => ({
  supabase: { auth: { getUser: () => Promise.resolve({ data: { user: null }, error: null }) } },
}));

// Mock layout — return content without wrapping
mock.module("../../src/views/layout", () => ({
  layout: (title: string, content: unknown, user: unknown, opts?: unknown) =>
    `<html><title>${title}</title><body>${content}</body></html>`,
}));

// Mock vote widget
mock.module("../../src/views/components/vote-widget", () => ({
  voteWidget: (name: string, score: number, userVote: number, showDown: boolean) =>
    `<div class="vote-widget" data-name="${name}" data-score="${score}"></div>`,
}));

// Mock comment section
mock.module("../../src/views/components/comment-section", () => ({
  commentSection: (name: string, comments: unknown[], user: unknown) =>
    `<div id="comments-section">${(comments as unknown[]).length} comments</div>`,
  commentBody: () => "<div>comment</div>",
}));

const { pageRoutes } = await import("../../src/routes/pages");

// ---------------------------------------------------------------------------
// App factory
// ---------------------------------------------------------------------------

function createPageApp(user: AppUser | null = null): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });
  app.route("/", pageRoutes);
  return app;
}

// ---------------------------------------------------------------------------
// Tests: GET / (Catalogue)
// ---------------------------------------------------------------------------

describe("GET / (Catalogue)", () => {
  beforeEach(() => {
    mockPluginRows = [MOCK_PLUGIN];
    mockTotalCount = 1;
  });

  test("returns 200 with catalogue page", async () => {
    const app = createPageApp();
    const res = await app.request("/");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Catalogue");
    expect(html).toContain("Plugin Catalogue");
  });

  test("renders plugin cards in results", async () => {
    const app = createPageApp();
    const res = await app.request("/");
    const html = await res.text();
    expect(html).toContain("test-plugin");
    expect(html).toContain("42 installs");
  });

  test("shows empty message when no plugins", async () => {
    mockPluginRows = [];
    mockTotalCount = 0;
    const app = createPageApp();
    const res = await app.request("/");
    const html = await res.text();
    expect(html).toContain("No plugins found");
  });

  test("includes search input with query value", async () => {
    const app = createPageApp();
    const res = await app.request("/?q=cool");
    const html = await res.text();
    expect(html).toContain("Search plugins");
  });

  test("renders sort dropdown with all options", async () => {
    const app = createPageApp();
    const res = await app.request("/");
    const html = await res.text();
    expect(html).toContain("Trending");
    expect(html).toContain("Most installed");
    expect(html).toContain("Highest voted");
    expect(html).toContain("Newest");
    expect(html).toContain("Recently updated");
  });

  test("accepts sort parameter", async () => {
    const app = createPageApp();
    const res = await app.request("/?sort=newest");
    expect(res.status).toBe(200);
  });

  test("defaults to trending for invalid sort", async () => {
    const app = createPageApp();
    const res = await app.request("/?sort=invalid");
    expect(res.status).toBe(200);
  });

  test("handles page parameter", async () => {
    const app = createPageApp();
    const res = await app.request("/?page=1");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Page 2");
  });

  test("clamps negative page to 0", async () => {
    const app = createPageApp();
    const res = await app.request("/?page=-5");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Page 1");
  });

  test("works for authenticated users", async () => {
    const app = createPageApp(mockUser());
    const res = await app.request("/");
    expect(res.status).toBe(200);
  });
});

// ---------------------------------------------------------------------------
// Tests: GET /partials/plugin-list (HTMX partial)
// ---------------------------------------------------------------------------

describe("GET /partials/plugin-list", () => {
  beforeEach(() => {
    mockPluginRows = [MOCK_PLUGIN];
    mockTotalCount = 1;
  });

  test("returns 200 with plugin list partial (no layout)", async () => {
    const app = createPageApp();
    const res = await app.request("/partials/plugin-list");
    expect(res.status).toBe(200);
    const html = await res.text();
    // Should NOT contain <html> tag (it's a partial)
    expect(html).not.toContain("<html>");
    expect(html).toContain("test-plugin");
  });

  test("shows empty message for no results", async () => {
    mockPluginRows = [];
    mockTotalCount = 0;
    const app = createPageApp();
    const res = await app.request("/partials/plugin-list");
    const html = await res.text();
    expect(html).toContain("No plugins found");
  });

  test("shows search query in empty message", async () => {
    mockPluginRows = [];
    mockTotalCount = 0;
    const app = createPageApp();
    const res = await app.request("/partials/plugin-list?q=foobar");
    const html = await res.text();
    expect(html).toContain("foobar");
  });

  test("renders pagination links", async () => {
    mockTotalCount = 50; // multiple pages
    const app = createPageApp();
    const res = await app.request("/partials/plugin-list?page=1");
    const html = await res.text();
    expect(html).toContain("Previous");
    expect(html).toContain("Page 2");
  });
});

// ---------------------------------------------------------------------------
// Tests: GET /plugins/:name (Plugin detail)
// ---------------------------------------------------------------------------

describe("GET /plugins/:name", () => {
  beforeEach(() => {
    mockDetailPlugin = MOCK_PLUGIN;
    mockSkills = [];
    mockUserVoteRows = [];
    mockCommentRows = [];
  });

  test("returns 200 with plugin detail page", async () => {
    const app = createPageApp();
    const res = await app.request("/plugins/test-plugin");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("test-plugin");
    expect(html).toContain("A test plugin");
  });

  test("returns 404 when plugin not found", async () => {
    mockDetailPlugin = null;
    const app = createPageApp();
    const res = await app.request("/plugins/nonexistent");
    expect(res.status).toBe(404);
    const html = await res.text();
    expect(html).toContain("Plugin not found");
    expect(html).toContain("nonexistent");
  });

  test("renders install instructions", async () => {
    const app = createPageApp();
    const res = await app.request("/plugins/test-plugin");
    const html = await res.text();
    expect(html).toContain("uvx openforge add");
    expect(html).toContain("npx skills add");
  });

  test("renders metadata section", async () => {
    const app = createPageApp();
    const res = await app.request("/plugins/test-plugin");
    const html = await res.text();
    expect(html).toContain("productivity");
    expect(html).toContain("abc123def456");
    expect(html).toContain("42");
  });

  test("renders README HTML", async () => {
    const app = createPageApp();
    const res = await app.request("/plugins/test-plugin");
    const html = await res.text();
    expect(html).toContain("Hello");
  });

  test("renders comment section", async () => {
    const app = createPageApp();
    const res = await app.request("/plugins/test-plugin");
    const html = await res.text();
    expect(html).toContain("comments-section");
  });

  test("renders vote widget on detail page", async () => {
    const app = createPageApp();
    const res = await app.request("/plugins/test-plugin");
    const html = await res.text();
    // Vote widget HTML is entity-escaped by Hono's html`` template
    expect(html).toContain("vote-widget");
  });

  test("works for authenticated users", async () => {
    const app = createPageApp(mockUser());
    const res = await app.request("/plugins/test-plugin");
    expect(res.status).toBe(200);
  });
});
