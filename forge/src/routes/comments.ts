// forge/src/routes/comments.ts
import { Hono } from "hono";
import { eq } from "drizzle-orm";
import { db } from "../db";
import { comments, plugins, users } from "../db/schema";
import { requireAuth } from "../middleware/auth";
import { checkRateLimit } from "../lib/rate-limit";
import { renderMarkdown } from "../lib/markdown";
import type { AppEnv } from "../types";
import { commentSection } from "../views/components/comment-section";
import { html, raw } from "hono/html";

export const commentRoutes = new Hono<AppEnv>();

const MAX_BODY_LENGTH = 10_000;

// ---------------------------------------------------------------------------
// Helper: validate plugin exists, return its ID
// ---------------------------------------------------------------------------

async function getPluginId(name: string): Promise<string | null> {
  const [plugin] = await db
    .select({ id: plugins.id })
    .from(plugins)
    .where(eq(plugins.name, name))
    .limit(1);
  return plugin?.id ?? null;
}

// ---------------------------------------------------------------------------
// Helper: load all comments for a plugin with user info
// ---------------------------------------------------------------------------

async function loadComments(pluginId: string) {
  return db
    .select({
      id: comments.id,
      body: comments.body,
      parentId: comments.parentId,
      createdAt: comments.createdAt,
      updatedAt: comments.updatedAt,
      userId: comments.userId,
      userEmail: users.email,
      userDisplayName: users.displayName,
    })
    .from(comments)
    .innerJoin(users, eq(comments.userId, users.id))
    .where(eq(comments.pluginId, pluginId));
}

// ---------------------------------------------------------------------------
// POST /plugins/:name/comments — create comment
// ---------------------------------------------------------------------------

commentRoutes.post("/plugins/:name/comments", async (c) => {
  const user = requireAuth(c);
  const pluginName = c.req.param("name");

  // Rate limit: 5 comments per user per minute
  if (!checkRateLimit(`comment:${user.id}`, 5, 60_000)) {
    return c.text("Too many requests", 429);
  }

  const pluginId = await getPluginId(pluginName);
  if (!pluginId) return c.text("Plugin not found", 404);

  // Parse body — support both JSON and form data
  let body: string;
  let parentId: string | null = null;

  const contentType = c.req.header("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const json = await c.req.json();
    body = String(json.body ?? "").trim();
    parentId = json.parent_id ?? null;
  } else {
    const form = await c.req.parseBody();
    body = String(form.body ?? "").trim();
    parentId = form.parent_id ? String(form.parent_id) : null;
  }

  // Validate body
  if (!body || body.length === 0) {
    return c.text("Comment body is required", 400);
  }
  if (body.length > MAX_BODY_LENGTH) {
    return c.text(`Comment body exceeds ${MAX_BODY_LENGTH} characters`, 400);
  }

  // Validate parent_id — enforce one-level nesting
  if (parentId) {
    const [parent] = await db
      .select({
        id: comments.id,
        parentId: comments.parentId,
        pluginId: comments.pluginId,
      })
      .from(comments)
      .where(eq(comments.id, parentId))
      .limit(1);

    if (!parent) {
      return c.text("Parent comment not found", 400);
    }
    if (parent.pluginId !== pluginId) {
      return c.text("Parent comment belongs to a different plugin", 400);
    }
    if (parent.parentId !== null) {
      return c.text("Cannot reply to a reply (one-level nesting only)", 400);
    }
  }

  // Insert comment
  const [inserted] = await db
    .insert(comments)
    .values({
      pluginId,
      userId: user.id,
      parentId,
      body,
    })
    .returning();

  // Return HTMX partial for the new comment
  const renderedBody = renderMarkdown(inserted.body);
  const displayName = user.displayName ?? user.email.split("@")[0];
  const isReply = !!parentId;

  return c.html(html`
    <div
      id="comment-${inserted.id}"
      class="${isReply
        ? "ml-8 border-l-2 border-gray-200 pl-4"
        : ""} py-3"
    >
      <div class="flex items-center gap-2 text-sm text-gray-500 mb-1">
        <span class="font-medium text-gray-700">${displayName}</span>
        <span>&middot;</span>
        <time>just now</time>
      </div>
      <div class="prose prose-sm max-w-none">${raw(renderedBody)}</div>
    </div>
  `);
});

// ---------------------------------------------------------------------------
// PATCH /plugins/:name/comments/:id — edit own comment
// ---------------------------------------------------------------------------

commentRoutes.patch("/plugins/:name/comments/:id", async (c) => {
  const user = requireAuth(c);
  const commentId = c.req.param("id");

  // Verify ownership
  const [comment] = await db
    .select()
    .from(comments)
    .where(eq(comments.id, commentId))
    .limit(1);

  if (!comment) return c.text("Comment not found", 404);
  if (comment.userId !== user.id) return c.text("Not your comment", 403);

  // Parse body
  const contentType = c.req.header("content-type") ?? "";
  let body: string;
  if (contentType.includes("application/json")) {
    const json = await c.req.json();
    body = String(json.body ?? "").trim();
  } else {
    const form = await c.req.parseBody();
    body = String(form.body ?? "").trim();
  }

  if (!body || body.length > MAX_BODY_LENGTH) {
    return c.text("Invalid comment body", 400);
  }

  // Update
  const [updated] = await db
    .update(comments)
    .set({ body, updatedAt: new Date() })
    .where(eq(comments.id, commentId))
    .returning();

  const renderedBody = renderMarkdown(updated.body);
  const displayName = user.displayName ?? user.email.split("@")[0];
  const pluginName = c.req.param("name");

  return c.html(html`
    <div
      id="comment-${updated.id}"
      class="${updated.parentId
        ? "ml-8 border-l-2 border-gray-200 pl-4"
        : ""} py-3"
    >
      <div class="flex items-center gap-2 text-sm text-gray-500 mb-1">
        <span class="font-medium text-gray-700">${displayName}</span>
        <span>&middot;</span>
        <time>${updated.createdAt.toLocaleDateString()}</time>
        <span class="italic">(edited)</span>
      </div>
      <div class="prose prose-sm max-w-none">${raw(renderedBody)}</div>
      <div class="flex gap-3 mt-2 text-sm">
        <button
          hx-get="/plugins/${pluginName}/comments/${updated.id}/edit"
          hx-target="#comment-${updated.id}"
          hx-swap="outerHTML"
          class="text-gray-500 hover:text-gray-700"
        >
          Edit
        </button>
        <button
          hx-delete="/plugins/${pluginName}/comments/${updated.id}"
          hx-target="#comment-${updated.id}"
          hx-swap="delete"
          hx-confirm="Delete this comment?"
          class="text-red-500 hover:text-red-700"
        >
          Delete
        </button>
      </div>
    </div>
  `);
});

// ---------------------------------------------------------------------------
// GET /plugins/:name/comments/:id/edit — edit form partial
// ---------------------------------------------------------------------------

commentRoutes.get("/plugins/:name/comments/:id/edit", async (c) => {
  const user = requireAuth(c);
  const commentId = c.req.param("id");
  const pluginName = c.req.param("name");

  const [comment] = await db
    .select()
    .from(comments)
    .where(eq(comments.id, commentId))
    .limit(1);

  if (!comment) return c.text("Comment not found", 404);
  if (comment.userId !== user.id) return c.text("Not your comment", 403);

  return c.html(html`
    <div
      id="comment-${comment.id}"
      class="${comment.parentId
        ? "ml-8 border-l-2 border-gray-200 pl-4"
        : ""} py-3"
    >
      <form
        hx-patch="/plugins/${pluginName}/comments/${comment.id}"
        hx-target="#comment-${comment.id}"
        hx-swap="outerHTML"
      >
        <textarea
          name="body"
          required
          maxlength="10000"
          rows="4"
          class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        >${comment.body}</textarea>
        <div class="flex gap-2 mt-2">
          <button
            type="submit"
            class="px-4 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
          >
            Save
          </button>
          <button
            type="button"
            hx-get="/plugins/${pluginName}/comments"
            hx-target="#comments-section"
            hx-swap="outerHTML"
            class="px-4 py-1.5 bg-gray-100 text-gray-700 text-sm rounded hover:bg-gray-200"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  `);
});

// ---------------------------------------------------------------------------
// DELETE /plugins/:name/comments/:id — delete own comment
// ---------------------------------------------------------------------------

commentRoutes.delete("/plugins/:name/comments/:id", async (c) => {
  const user = requireAuth(c);
  const commentId = c.req.param("id");

  const [comment] = await db
    .select()
    .from(comments)
    .where(eq(comments.id, commentId))
    .limit(1);

  if (!comment) return c.text("Comment not found", 404);
  if (comment.userId !== user.id) return c.text("Not your comment", 403);

  // Delete replies first (if top-level comment)
  if (!comment.parentId) {
    await db.delete(comments).where(eq(comments.parentId, commentId));
  }

  await db.delete(comments).where(eq(comments.id, commentId));

  return c.body(null, 200);
});

// ---------------------------------------------------------------------------
// GET /plugins/:name/comments — full comments section partial
// ---------------------------------------------------------------------------

commentRoutes.get("/plugins/:name/comments", async (c) => {
  const user = c.get("user");
  const pluginName = c.req.param("name");

  const pluginId = await getPluginId(pluginName);
  if (!pluginId) return c.text("Plugin not found", 404);

  const allComments = await loadComments(pluginId);
  return c.html(commentSection(pluginName, allComments, user));
});
