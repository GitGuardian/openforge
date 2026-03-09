import { describe, expect, test, mock, beforeEach } from "bun:test";
import { Hono } from "hono";
import type { AppEnv, AppUser } from "../../src/types";
import { mockUser } from "../setup";

// ---------------------------------------------------------------------------
// Configurable mock state
// ---------------------------------------------------------------------------

const PLUGIN_ID = "plugin-001";
const COMMENT_ID = "c0000000-0000-0000-0000-000000000001";
const REPLY_ID = "c0000000-0000-0000-0000-000000000002";

let currentUser: AppUser | null = mockUser();
let mockPluginId: string | null = PLUGIN_ID;

// Comments stored in mock "database"
let mockComments: Array<{
  id: string;
  body: string;
  parentId: string | null;
  pluginId: string;
  userId: string;
  createdAt: Date;
  updatedAt: Date;
}> = [];

let insertedComment: Record<string, unknown> | null = null;
let updatedComment: Record<string, unknown> | null = null;
let deletedIds: string[] = [];
let transactionDeletedIds: string[] = [];

// ---------------------------------------------------------------------------
// Mock modules
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    select: (fields: unknown) => ({
      from: (table: unknown) => ({
        where: (cond: unknown) => ({
          limit: () => {
            // Distinguish by fields shape
            if (fields && typeof fields === "object" && "id" in fields && Object.keys(fields).length === 1) {
              // getPluginId lookup — returns { id }
              return Promise.resolve(mockPluginId ? [{ id: mockPluginId }] : []);
            }
            // Comment lookup — return first matching comment
            // We use a simple heuristic: return the first mock comment
            if (mockComments.length > 0) {
              return Promise.resolve([mockComments[0]]);
            }
            return Promise.resolve([]);
          },
        }),
        innerJoin: () => ({
          where: () => Promise.resolve([]), // loadComments returns empty for simplicity
        }),
      }),
    }),
    insert: (table: unknown) => ({
      values: (values: Record<string, unknown>) => ({
        returning: () => {
          insertedComment = values;
          return Promise.resolve([{
            id: "new-comment-id",
            body: values.body,
            parentId: values.parentId ?? null,
            pluginId: values.pluginId,
            userId: values.userId,
            createdAt: new Date(),
            updatedAt: new Date(),
          }]);
        },
      }),
    }),
    update: (table: unknown) => ({
      set: (values: Record<string, unknown>) => ({
        where: (cond: unknown) => ({
          returning: () => {
            updatedComment = values;
            return Promise.resolve([{
              id: COMMENT_ID,
              body: values.body ?? "updated body",
              parentId: null,
              createdAt: new Date(),
              updatedAt: new Date(),
            }]);
          },
        }),
      }),
    }),
    delete: (table: unknown) => ({
      where: (cond: unknown) => {
        deletedIds.push("deleted");
        return Promise.resolve();
      },
    }),
    transaction: async (fn: (tx: unknown) => Promise<unknown>) => {
      const tx = {
        delete: (table: unknown) => ({
          where: (cond: unknown) => {
            transactionDeletedIds.push("deleted");
            return Promise.resolve();
          },
        }),
      };
      return fn(tx);
    },
  },
}));

// Mock auth
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

// Mock rate limiter
let rateLimitAllowed = true;
mock.module("../../src/lib/rate-limit", () => ({
  checkRateLimit: () => rateLimitAllowed,
}));

// Mock comment-section view components
mock.module("../../src/views/components/comment-section", () => ({
  commentSection: (name: string, comments: unknown[], user: unknown) =>
    `<div id="comments-section">${(comments as unknown[]).length} comments</div>`,
  commentBody: (row: Record<string, unknown>, user: unknown, name: string, isReply: boolean) =>
    `<div class="comment" data-id="${row.id}" data-body="${row.body}" data-reply="${isReply}"></div>`,
}));

// Import AFTER mocking
const { commentRoutes } = await import("../../src/routes/comments");

// ---------------------------------------------------------------------------
// Test app factory
// ---------------------------------------------------------------------------

function createCommentApp(user: AppUser | null = mockUser()): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });
  app.onError((err, c) => {
    const status = (err as { status?: number }).status ?? 500;
    return c.text(err.message, status as 401 | 403 | 500);
  });
  app.route("/", commentRoutes);
  return app;
}

// ---------------------------------------------------------------------------
// Tests: POST /plugins/:name/comments
// ---------------------------------------------------------------------------

describe("POST /plugins/:name/comments", () => {
  beforeEach(() => {
    currentUser = mockUser();
    mockPluginId = PLUGIN_ID;
    mockComments = [];
    insertedComment = null;
    updatedComment = null;
    deletedIds = [];
    transactionDeletedIds = [];
    rateLimitAllowed = true;
  });

  test("rejects unauthenticated users with 401", async () => {
    const app = createCommentApp(null);
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "hello" }),
    });
    expect(res.status).toBe(401);
  });

  test("returns 429 when rate limited", async () => {
    rateLimitAllowed = false;
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "hello" }),
    });
    expect(res.status).toBe(429);
  });

  test("returns 404 when plugin does not exist", async () => {
    mockPluginId = null;
    const app = createCommentApp();
    const res = await app.request("/plugins/nonexistent/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "hello" }),
    });
    expect(res.status).toBe(404);
  });

  test("rejects empty comment body", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "" }),
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Comment body is required");
  });

  test("rejects comment body exceeding 10000 characters", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "x".repeat(10_001) }),
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toContain("10000");
  });

  test("rejects invalid parent_id UUID format", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "reply", parent_id: "not-a-uuid" }),
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Invalid parent_id format");
  });

  test("rejects reply to non-existent parent", async () => {
    mockComments = []; // no comments in DB
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        body: "reply",
        parent_id: COMMENT_ID,
      }),
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Parent comment not found");
  });

  test("rejects reply to a reply (nesting limit)", async () => {
    mockComments = [{
      id: REPLY_ID,
      body: "I'm a reply",
      parentId: COMMENT_ID, // has a parent — is already a reply
      pluginId: PLUGIN_ID,
      userId: "other-user",
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        body: "reply to reply",
        parent_id: REPLY_ID,
      }),
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Cannot reply to a reply (one-level nesting only)");
  });

  test("rejects reply to comment on different plugin", async () => {
    mockComments = [{
      id: COMMENT_ID,
      body: "wrong plugin comment",
      parentId: null,
      pluginId: "other-plugin-id", // different plugin
      userId: "other-user",
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        body: "cross-plugin reply",
        parent_id: COMMENT_ID,
      }),
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Parent comment belongs to a different plugin");
  });

  test("creates top-level comment successfully", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "Great plugin!" }),
    });
    expect(res.status).toBe(200);
    expect(insertedComment).not.toBeNull();
    expect(insertedComment!.body).toBe("Great plugin!");
    expect(insertedComment!.parentId).toBeNull();
    expect(insertedComment!.pluginId).toBe(PLUGIN_ID);

    const html = await res.text();
    expect(html).toContain("comment");
    expect(html).toContain('data-reply="false"');
  });

  test("creates reply comment successfully", async () => {
    mockComments = [{
      id: COMMENT_ID,
      body: "parent comment",
      parentId: null,
      pluginId: PLUGIN_ID,
      userId: "other-user",
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        body: "Reply text",
        parent_id: COMMENT_ID,
      }),
    });
    expect(res.status).toBe(200);
    expect(insertedComment!.parentId).toBe(COMMENT_ID);

    const html = await res.text();
    expect(html).toContain('data-reply="true"');
  });

  test("accepts form-encoded body", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "body=Form+comment",
    });
    expect(res.status).toBe(200);
    expect(insertedComment!.body).toBe("Form comment");
  });
});

// ---------------------------------------------------------------------------
// Tests: PATCH /plugins/:name/comments/:id
// ---------------------------------------------------------------------------

describe("PATCH /plugins/:name/comments/:id", () => {
  beforeEach(() => {
    mockComments = [{
      id: COMMENT_ID,
      body: "original body",
      parentId: null,
      pluginId: PLUGIN_ID,
      userId: mockUser().id,
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    updatedComment = null;
  });

  test("rejects unauthenticated users", async () => {
    const app = createCommentApp(null);
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "updated" }),
    });
    expect(res.status).toBe(401);
  });

  test("rejects invalid comment ID format", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments/not-a-uuid", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "updated" }),
    });
    expect(res.status).toBe(400);
    const text = await res.text();
    expect(text).toBe("Invalid comment ID");
  });

  test("returns 404 when comment does not exist", async () => {
    mockComments = [];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "updated" }),
    });
    expect(res.status).toBe(404);
  });

  test("rejects editing someone else's comment (403)", async () => {
    mockComments = [{
      id: COMMENT_ID,
      body: "not yours",
      parentId: null,
      pluginId: PLUGIN_ID,
      userId: "other-user-id", // different user
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "hijacked" }),
    });
    expect(res.status).toBe(403);
    const text = await res.text();
    expect(text).toBe("Not your comment");
  });

  test("rejects empty edit body", async () => {
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "" }),
    });
    expect(res.status).toBe(400);
  });

  test("edits own comment successfully", async () => {
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "edited text" }),
    });
    expect(res.status).toBe(200);
    expect(updatedComment).not.toBeNull();
    expect(updatedComment!.body).toBe("edited text");
  });

  test("accepts form-encoded edit body", async () => {
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "body=form+edited",
    });
    expect(res.status).toBe(200);
    expect(updatedComment!.body).toBe("form edited");
  });
});

// ---------------------------------------------------------------------------
// Tests: GET /plugins/:name/comments/:id/edit
// ---------------------------------------------------------------------------

describe("GET /plugins/:name/comments/:id/edit", () => {
  beforeEach(() => {
    mockComments = [{
      id: COMMENT_ID,
      body: "original body",
      parentId: null,
      pluginId: PLUGIN_ID,
      userId: mockUser().id,
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
  });

  test("rejects unauthenticated users", async () => {
    const app = createCommentApp(null);
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}/edit`);
    expect(res.status).toBe(401);
  });

  test("rejects invalid comment ID", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments/bad-id/edit");
    expect(res.status).toBe(400);
  });

  test("returns 404 when comment does not exist", async () => {
    mockComments = [];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}/edit`);
    expect(res.status).toBe(404);
  });

  test("rejects editing someone else's comment", async () => {
    mockComments = [{
      id: COMMENT_ID,
      body: "not mine",
      parentId: null,
      pluginId: PLUGIN_ID,
      userId: "other-user-id",
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}/edit`);
    expect(res.status).toBe(403);
  });

  test("returns edit form HTML for own comment", async () => {
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}/edit`);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("textarea");
    expect(html).toContain("original body");
    expect(html).toContain("hx-patch");
    expect(html).toContain("Save");
  });

  test("renders nested comment edit form with indent class", async () => {
    mockComments = [{
      id: COMMENT_ID,
      body: "a reply",
      parentId: "parent-id",
      pluginId: PLUGIN_ID,
      userId: mockUser().id,
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}/edit`);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("ml-8");
  });
});

// ---------------------------------------------------------------------------
// Tests: DELETE /plugins/:name/comments/:id
// ---------------------------------------------------------------------------

describe("DELETE /plugins/:name/comments/:id", () => {
  beforeEach(() => {
    mockComments = [{
      id: COMMENT_ID,
      body: "to delete",
      parentId: null,
      pluginId: PLUGIN_ID,
      userId: mockUser().id,
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    deletedIds = [];
    transactionDeletedIds = [];
  });

  test("rejects unauthenticated users", async () => {
    const app = createCommentApp(null);
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "DELETE",
    });
    expect(res.status).toBe(401);
  });

  test("rejects invalid comment ID format", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments/bad-id", {
      method: "DELETE",
    });
    expect(res.status).toBe(400);
  });

  test("returns 404 when comment does not exist", async () => {
    mockComments = [];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "DELETE",
    });
    expect(res.status).toBe(404);
  });

  test("rejects deleting someone else's comment (403)", async () => {
    mockComments = [{
      id: COMMENT_ID,
      body: "not yours",
      parentId: null,
      pluginId: PLUGIN_ID,
      userId: "other-user-id",
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "DELETE",
    });
    expect(res.status).toBe(403);
  });

  test("deletes own top-level comment (cascades replies)", async () => {
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${COMMENT_ID}`, {
      method: "DELETE",
    });
    expect(res.status).toBe(200);
    // Transaction should delete replies then parent (2 deletes)
    expect(transactionDeletedIds).toHaveLength(2);
  });

  test("deletes own reply (no cascade)", async () => {
    mockComments = [{
      id: REPLY_ID,
      body: "a reply",
      parentId: COMMENT_ID, // is a reply
      pluginId: PLUGIN_ID,
      userId: mockUser().id,
      createdAt: new Date(),
      updatedAt: new Date(),
    }];
    const app = createCommentApp();
    const res = await app.request(`/plugins/test/comments/${REPLY_ID}`, {
      method: "DELETE",
    });
    expect(res.status).toBe(200);
    // Reply delete: only 1 delete (no cascade)
    expect(transactionDeletedIds).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Tests: GET /plugins/:name/comments
// ---------------------------------------------------------------------------

describe("GET /plugins/:name/comments", () => {
  beforeEach(() => {
    mockPluginId = PLUGIN_ID;
  });

  test("returns 404 when plugin does not exist", async () => {
    mockPluginId = null;
    const app = createCommentApp();
    const res = await app.request("/plugins/nonexistent/comments");
    expect(res.status).toBe(404);
  });

  test("returns comments section HTML", async () => {
    const app = createCommentApp();
    const res = await app.request("/plugins/test/comments");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("comments-section");
  });

  test("works for unauthenticated users", async () => {
    const app = createCommentApp(null);
    const res = await app.request("/plugins/test/comments");
    expect(res.status).toBe(200);
  });
});
