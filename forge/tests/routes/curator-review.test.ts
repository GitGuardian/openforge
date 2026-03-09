import { describe, expect, test, mock, beforeEach } from "bun:test";
import { Hono } from "hono";
import type { AppEnv, AppUser } from "../../src/types";
import { mockUser } from "../setup";

// ---------------------------------------------------------------------------
// Mock state
// ---------------------------------------------------------------------------

let mockDetailPlugin: Record<string, unknown> | null = null;
let mockSubmissionRows: unknown[] = [];

const APPROVED_PLUGIN = {
  id: "plugin-001",
  registryId: "reg-001",
  name: "test-plugin",
  version: "1.0.0",
  description: "A test plugin",
  category: "productivity",
  tags: ["ai"],
  readmeHtml: "<p>Hello</p>",
  pluginJson: {},
  gitPath: "owner/repo",
  gitSha: "abc123",
  status: "approved",
  installCount: 10,
  voteScore: 5,
  createdAt: new Date(),
  updatedAt: new Date(),
};

const PENDING_PLUGIN = {
  ...APPROVED_PLUGIN,
  name: "pending-plugin",
  status: "pending",
};

// ---------------------------------------------------------------------------
// Mock modules — focused mock for detail page + submission query
// ---------------------------------------------------------------------------

// Track which "table" is being queried by intercepting from()
let querySequence: string[] = [];
let queryIndex = 0;

mock.module("../../src/db", () => {
  const makeSelectResult = (fields?: unknown) => {
    // Vote value select
    if (fields && typeof fields === "object" && "value" in fields && !("total" in fields)) {
      return {
        from: () => ({
          where: () => ({
            limit: () => Promise.resolve([]),
          }),
        }),
      };
    }
    // Count select
    if (fields && typeof fields === "object" && "total" in fields) {
      return {
        from: () => ({
          where: () => Promise.resolve([{ total: 1 }]),
        }),
      };
    }
    // Regular select — uses queryIndex to differentiate sequential calls
    return {
      from: () => {
        const idx = queryIndex++;
        return {
          // Plugin detail: .where().limit(1)
          where: () => {
            // First where().limit() is the plugin query
            // Second where().limit() is the submissions query (if pending)
            if (idx === 0) {
              return {
                limit: () => Promise.resolve(mockDetailPlugin ? [mockDetailPlugin] : []),
                orderBy: () => ({
                  limit: () => ({
                    offset: () => Promise.resolve([]),
                  }),
                }),
                then: (resolve: (v: unknown) => unknown, reject?: (e: unknown) => unknown) =>
                  Promise.resolve([]).then(resolve, reject),
              };
            }
            // Skills query (idx === 1) — thenable
            if (idx === 1) {
              return {
                limit: () => Promise.resolve(mockSubmissionRows),
                then: (resolve: (v: unknown) => unknown, reject?: (e: unknown) => unknown) =>
                  Promise.resolve([]).then(resolve, reject),
              };
            }
            // Submission query (idx === 2+) — limit()
            return {
              limit: () => Promise.resolve(mockSubmissionRows),
              then: (resolve: (v: unknown) => unknown, reject?: (e: unknown) => unknown) =>
                Promise.resolve(mockSubmissionRows).then(resolve, reject),
            };
          },
          innerJoin: () => ({
            where: () => Promise.resolve([]),
          }),
          leftJoin: () => ({
            where: () => ({
              orderBy: () => ({
                limit: () => ({
                  offset: () => Promise.resolve([]),
                }),
              }),
            }),
          }),
        };
      },
    };
  };
  return { db: { select: makeSelectResult } };
});

mock.module("../../src/lib/supabase", () => ({
  supabase: { auth: { getUser: () => Promise.resolve({ data: { user: null }, error: null }) } },
}));

mock.module("../../src/views/layout", () => ({
  layout: (title: string, content: unknown, user: unknown) =>
    `<html><title>${title}</title><body>${content}</body></html>`,
}));

mock.module("../../src/views/components/vote-widget", () => ({
  voteWidget: () => `<div class="vote-widget"></div>`,
}));

mock.module("../../src/views/components/comment-section", () => ({
  commentSection: () => `<div id="comments-section"></div>`,
  commentBody: () => "<div>comment</div>",
}));

const { pageRoutes } = await import("../../src/routes/pages");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const curator = mockUser({ role: "curator", id: "curator-001" });
const regularUser = mockUser({ role: "user", id: "user-001" });

function createApp(user: AppUser | null = null) {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });
  app.route("/", pageRoutes);
  return app;
}

// ---------------------------------------------------------------------------
// Tests: Curator review on plugin detail page
// ---------------------------------------------------------------------------

describe("GET /plugins/:name (curator review)", () => {
  beforeEach(() => {
    mockDetailPlugin = null;
    mockSubmissionRows = [];
    queryIndex = 0;
  });

  test("curator sees review banner for pending plugin", async () => {
    mockDetailPlugin = PENDING_PLUGIN;
    mockSubmissionRows = [{
      id: "sub-001",
      userId: "user-001",
      gitUrl: "https://github.com/owner/repo",
      description: "A cool plugin",
    }];
    const app = createApp(curator);
    const res = await app.request("/plugins/pending-plugin");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("pending review");
    expect(html).toContain("Approve");
    expect(html).toContain("Reject");
  });

  test("regular user gets 404 for pending plugin", async () => {
    mockDetailPlugin = PENDING_PLUGIN;
    const app = createApp(regularUser);
    const res = await app.request("/plugins/pending-plugin");
    expect(res.status).toBe(404);
  });

  test("unauthenticated user gets 404 for pending plugin", async () => {
    mockDetailPlugin = PENDING_PLUGIN;
    const app = createApp(null);
    const res = await app.request("/plugins/pending-plugin");
    expect(res.status).toBe(404);
  });

  test("curator sees no review banner for approved plugin", async () => {
    mockDetailPlugin = APPROVED_PLUGIN;
    const app = createApp(curator);
    const res = await app.request("/plugins/test-plugin");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).not.toContain("pending review");
  });

  test("review banner contains submission git URL", async () => {
    mockDetailPlugin = PENDING_PLUGIN;
    mockSubmissionRows = [{
      id: "sub-001",
      userId: "user-001",
      gitUrl: "https://github.com/owner/repo",
      description: null,
    }];
    const app = createApp(curator);
    const res = await app.request("/plugins/pending-plugin");
    const html = await res.text();
    expect(html).toContain("https://github.com/owner/repo");
  });
});
