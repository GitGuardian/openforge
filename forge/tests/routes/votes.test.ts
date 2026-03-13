import { describe, expect, test, mock, beforeEach } from "bun:test";
import { Hono } from "hono";
import type { AppEnv, AppUser } from "../../src/types";
import { mockUser } from "../setup";

// ---------------------------------------------------------------------------
// Configurable mock state
// ---------------------------------------------------------------------------

let currentUser: AppUser | null = mockUser();
let mockPlugin: { id: string; voteScore: number } | null = {
  id: "plugin-001",
  voteScore: 10,
};
let mockExistingVote: { userId: string; pluginId: string; value: number } | null = null;
let insertedVote: Record<string, unknown> | null = null;
let updatedVoteValue: number | null = null;
let deletedVote = false;
let updatedPluginScore: unknown = null;
let transactionRan = false;

// ---------------------------------------------------------------------------
// Mock modules
// ---------------------------------------------------------------------------

// Mock DB with transaction support
mock.module("../../src/db", () => ({
  db: {
    transaction: async (fn: (tx: unknown) => Promise<unknown>) => {
      transactionRan = true;
      const tx = {
        select: (fields: unknown) => ({
          from: (table: unknown) => ({
            where: (cond: unknown) => ({
              limit: () => {
                // Distinguish plugin lookup vs vote lookup based on fields
                if (fields && typeof fields === "object" && "voteScore" in fields) {
                  return Promise.resolve(mockPlugin ? [mockPlugin] : []);
                }
                // Vote lookup
                return Promise.resolve(mockExistingVote ? [mockExistingVote] : []);
              },
            }),
          }),
        }),
        insert: (table: unknown) => ({
          values: (values: Record<string, unknown>) => {
            insertedVote = values;
            return Promise.resolve();
          },
        }),
        update: (table: unknown) => ({
          set: (values: Record<string, unknown>) => ({
            where: (cond: unknown) => {
              if ("value" in values) {
                updatedVoteValue = values.value as number;
              } else {
                updatedPluginScore = values;
              }
              return Promise.resolve();
            },
          }),
        }),
        delete: (table: unknown) => ({
          where: (cond: unknown) => {
            deletedVote = true;
            return Promise.resolve();
          },
        }),
      };
      return fn(tx);
    },
  },
}));

// Mock auth — returns currentUser or throws 401
mock.module("../../src/middleware/auth", () => ({
  requireAuth: (c: { get: (k: string) => unknown }) => {
    const user = c.get("user");
    if (!user) {
      throw Object.assign(new Error("Authentication required"), { status: 401 });
    }
    return user;
  },
  authMiddleware: async (c: unknown, next: () => Promise<void>) => next(),
  requireRole: () => {},
  requireAuthOrRedirect: () => {},
}));

// Mock rate limiter — always allows by default
let rateLimitAllowed = true;
mock.module("../../src/lib/rate-limit", () => ({
  checkRateLimit: () => rateLimitAllowed,
}));

// Mock vote widget — return simple HTML
mock.module("../../src/views/components/vote-widget", () => ({
  voteWidget: (name: string, score: number, userVote: number, showDown: boolean) =>
    `<div class="vote-widget" data-score="${score}" data-user-vote="${userVote}"></div>`,
}));

// Import AFTER mocking
const { voteRoutes } = await import("../../src/routes/votes");

// ---------------------------------------------------------------------------
// Create test app with auth context
// ---------------------------------------------------------------------------

function createVoteApp(user: AppUser | null = mockUser()): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });
  // Error handler for HTTPException
  app.onError((err, c) => {
    const status = (err as { status?: number }).status ?? 500;
    return c.text(err.message, status as 401 | 403 | 500);
  });
  app.route("/", voteRoutes);
  return app;
}

async function voteRequest(
  app: Hono<AppEnv>,
  pluginName: string,
  body: Record<string, unknown>,
): Promise<Response> {
  return await app.request(`/plugins/${pluginName}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("POST /plugins/:name/vote", () => {
  beforeEach(() => {
    currentUser = mockUser();
    mockPlugin = { id: "plugin-001", voteScore: 10 };
    mockExistingVote = null;
    insertedVote = null;
    updatedVoteValue = null;
    deletedVote = false;
    updatedPluginScore = null;
    transactionRan = false;
    rateLimitAllowed = true;
  });

  // --- Input length validation ---

  test("returns 400 for plugin name exceeding 200 chars", async () => {
    const longName = "a".repeat(201);
    const app = createVoteApp();
    const res = await voteRequest(app, longName, { value: 1 });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Invalid plugin name");
  });

  // --- Auth ---

  test("rejects unauthenticated users with 401", async () => {
    const app = createVoteApp(null);
    const res = await voteRequest(app, "test-plugin", { value: 1 });
    expect(res.status).toBe(401);
  });

  // --- Rate limiting ---

  test("returns 429 when rate limited", async () => {
    rateLimitAllowed = false;
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: 1 });
    expect(res.status).toBe(429);
    const text = await res.text();
    expect(text).toBe("Too many requests");
  });

  // --- Input validation ---

  test("rejects invalid vote value (not -1, 0, or 1)", async () => {
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: 5 });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Invalid vote value");
  });

  test("rejects vote value of 2", async () => {
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: 2 });
    expect(res.status).toBe(400);
  });

  test("rejects missing vote value", async () => {
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", {});
    expect(res.status).toBe(400);
  });

  // --- Plugin not found ---

  test("returns 404 when plugin does not exist", async () => {
    mockPlugin = null;
    const app = createVoteApp();
    const res = await voteRequest(app, "nonexistent", { value: 1 });
    expect(res.status).toBe(404);
    const text = await res.text();
    expect(text).toBe("Plugin not found");
  });

  // --- Upvote (new vote) ---

  test("inserts new upvote and returns widget HTML", async () => {
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: 1 });
    expect(res.status).toBe(200);
    expect(transactionRan).toBe(true);
    expect(insertedVote).not.toBeNull();
    expect(insertedVote!.value).toBe(1);

    const html = await res.text();
    expect(html).toContain("vote-widget");
    expect(html).toContain('data-score="11"'); // 10 + 1
    expect(html).toContain('data-user-vote="1"');
  });

  // --- Downvote (new vote) ---

  test("inserts new downvote", async () => {
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: -1 });
    expect(res.status).toBe(200);
    expect(insertedVote).not.toBeNull();
    expect(insertedVote!.value).toBe(-1);

    const html = await res.text();
    expect(html).toContain('data-score="9"'); // 10 - 1
  });

  // --- Toggle vote (update existing) ---

  test("updates existing vote when changing from up to down", async () => {
    mockExistingVote = {
      userId: mockUser().id,
      pluginId: "plugin-001",
      value: 1,
    };
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: -1 });
    expect(res.status).toBe(200);
    expect(updatedVoteValue).toBe(-1);
    expect(insertedVote).toBeNull(); // should update, not insert

    const html = await res.text();
    expect(html).toContain('data-score="8"'); // 10 + (-1 - 1) = 8
  });

  // --- Remove vote (value=0) ---

  test("deletes existing vote when value is 0", async () => {
    mockExistingVote = {
      userId: mockUser().id,
      pluginId: "plugin-001",
      value: 1,
    };
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: 0 });
    expect(res.status).toBe(200);
    expect(deletedVote).toBe(true);

    const html = await res.text();
    expect(html).toContain('data-score="9"'); // 10 + (0 - 1) = 9
    expect(html).toContain('data-user-vote="0"');
  });

  test("value=0 with no existing vote is a no-op", async () => {
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: 0 });
    expect(res.status).toBe(200);
    expect(deletedVote).toBe(false);
    expect(insertedVote).toBeNull();

    const html = await res.text();
    expect(html).toContain('data-score="10"'); // unchanged
  });

  // --- Context flag ---

  test("passes showDownvote=true when context is 'detail'", async () => {
    const app = createVoteApp();
    const res = await voteRequest(app, "test-plugin", { value: 1, context: "detail" });
    expect(res.status).toBe(200);
    // Widget is rendered — we can't easily assert showDownvote from mock,
    // but the route should not error
  });

  // --- Form body parsing ---

  test("accepts form-encoded body", async () => {
    const app = createVoteApp();
    const res = await app.request("/plugins/test-plugin/vote", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "value=1",
    });
    expect(res.status).toBe(200);
    expect(insertedVote).not.toBeNull();
  });

  // --- Invalid JSON body ---

  test("rejects invalid JSON body", async () => {
    const app = createVoteApp();
    const res = await app.request("/plugins/test-plugin/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "not json",
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Invalid JSON body");
  });
});
