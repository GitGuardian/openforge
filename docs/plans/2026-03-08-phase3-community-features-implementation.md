# Phase 3: Community Features — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add voting, threaded comments, and sort options to The Forge so users can interact with plugins beyond browsing.

**Architecture:** New route files for votes and comments (`forge/src/routes/votes.ts`, `forge/src/routes/comments.ts`) following the existing pattern in `api.ts` and `pages.ts`. HTMX partials for interactive updates. EasyMDE from CDN for comment editing. In-memory rate limiter for inline hardening. All data goes through existing Drizzle schema — no migrations needed.

**Tech Stack:** Hono routes, HTMX partials, Drizzle ORM, EasyMDE (CDN), Hono `csrf()` middleware, `marked` + `dompurify` (existing).

**Design doc:** `docs/plans/2026-03-08-phase3-community-features-design.md`

---

### Task 1: CSRF Middleware

Add Hono's built-in CSRF protection before any new POST routes exist. This is the foundation for all subsequent tasks.

**Files:**
- Modify: `forge/src/index.ts`

**Step 1: Add CSRF middleware**

In `forge/src/index.ts`, add the import and middleware registration:

```typescript
import { csrf } from "hono/csrf";
```

Add after the logger middleware, before route registration:

```typescript
app.use("*", csrf());
```

The full middleware section becomes:

```typescript
// Middleware
app.use("*", logger());
app.use("*", csrf());
app.use("*", authMiddleware);
```

**Step 2: Verify dev server starts**

Run: `cd forge && bun run dev`

Visit `http://localhost:3000` — catalogue should load. Try the search (HTMX GET requests unaffected by CSRF). Verify login/logout still works (POST forms include Origin header from the browser).

**Step 3: Verify typecheck passes**

Run: `cd forge && bun run typecheck`
Expected: 0 errors.

**Step 4: Commit**

```bash
git add forge/src/index.ts
git commit -m "feat(forge): add CSRF middleware"
```

---

### Task 2: In-Memory Rate Limiter

Simple rate limiter utility used by votes and comments routes. Replaced by proper rate limiting in Phase 6.

**Files:**
- Create: `forge/src/lib/rate-limit.ts`

**Step 1: Create the rate limiter**

```typescript
// forge/src/lib/rate-limit.ts

/**
 * Simple in-memory sliding-window rate limiter.
 * Tracks timestamps per key (user ID) and rejects if too many in the window.
 * Resets on server restart — good enough for local dev.
 * Replaced by proper middleware in Phase 6 (Hardening).
 */

const store = new Map<string, number[]>();

export function checkRateLimit(
  key: string,
  maxRequests: number,
  windowMs: number
): boolean {
  const now = Date.now();
  const timestamps = store.get(key) ?? [];

  // Prune expired timestamps
  const valid = timestamps.filter((t) => now - t < windowMs);

  if (valid.length >= maxRequests) {
    store.set(key, valid);
    return false; // rate limited
  }

  valid.push(now);
  store.set(key, valid);
  return true; // allowed
}
```

**Step 2: Verify typecheck passes**

Run: `cd forge && bun run typecheck`
Expected: 0 errors.

**Step 3: Commit**

```bash
git add forge/src/lib/rate-limit.ts
git commit -m "feat(forge): add in-memory rate limiter utility"
```

---

### Task 3: Vote Route

The core voting endpoint. Handles upvote, downvote, and remove-vote with HTMX partial response.

**Files:**
- Create: `forge/src/routes/votes.ts`
- Modify: `forge/src/index.ts` (register route)

**Step 1: Create the vote route**

```typescript
// forge/src/routes/votes.ts
import { Hono } from "hono";
import { eq, and, sql } from "drizzle-orm";
import { db } from "../db";
import { plugins, votes, users } from "../db/schema";
import { requireAuth } from "../middleware/auth";
import { checkRateLimit } from "../lib/rate-limit";
import type { AppEnv } from "../types";
import { voteWidget } from "../views/components/vote-widget";

export const voteRoutes = new Hono<AppEnv>();

// ---------------------------------------------------------------------------
// Downvote policy
// ---------------------------------------------------------------------------

function getDownvotePolicy(): { type: "authenticated" | "karma"; threshold: number } {
  const raw = process.env.DOWNVOTE_POLICY ?? (
    process.env.OPENFORGE_MODE === "private" ? "authenticated" : "karma:10"
  );

  if (raw === "authenticated") {
    return { type: "authenticated", threshold: 0 };
  }

  const match = raw.match(/^karma:(\d+)$/);
  if (match) {
    return { type: "karma", threshold: parseInt(match[1], 10) };
  }

  return { type: "authenticated", threshold: 0 };
}

async function canDownvote(userId: string): Promise<boolean> {
  const policy = getDownvotePolicy();
  if (policy.type === "authenticated") return true;

  // Count total upvotes received on user's plugins (karma)
  // For MVP: user needs to have received `threshold` upvotes across all their content
  // Since we don't have plugin_owners yet, we skip karma check and allow all authenticated
  // TODO: implement karma check when plugin_owners table is active
  return true;
}

// ---------------------------------------------------------------------------
// POST /plugins/:name/vote
// ---------------------------------------------------------------------------

voteRoutes.post("/plugins/:name/vote", async (c) => {
  const user = requireAuth(c);
  const pluginName = c.req.param("name");

  // Rate limit: 30 votes per user per minute
  if (!checkRateLimit(`vote:${user.id}`, 30, 60_000)) {
    return c.text("Too many requests", 429);
  }

  // Parse and validate value
  const body = await c.req.json();
  const value = body.value;
  if (value !== -1 && value !== 0 && value !== 1) {
    return c.text("Invalid vote value", 400);
  }

  // Check downvote permission
  if (value === -1) {
    const allowed = await canDownvote(user.id);
    if (!allowed) {
      return c.text("Downvoting not permitted", 403);
    }
  }

  // Find the plugin
  const [plugin] = await db
    .select({ id: plugins.id, voteScore: plugins.voteScore })
    .from(plugins)
    .where(eq(plugins.name, pluginName))
    .limit(1);

  if (!plugin) {
    return c.text("Plugin not found", 404);
  }

  // Get existing vote (if any)
  const [existingVote] = await db
    .select()
    .from(votes)
    .where(and(eq(votes.userId, user.id), eq(votes.pluginId, plugin.id)))
    .limit(1);

  const oldValue = existingVote?.value ?? 0;

  if (value === 0) {
    // Remove vote
    if (existingVote) {
      await db
        .delete(votes)
        .where(and(eq(votes.userId, user.id), eq(votes.pluginId, plugin.id)));
    }
  } else if (existingVote) {
    // Update existing vote
    await db
      .update(votes)
      .set({ value })
      .where(and(eq(votes.userId, user.id), eq(votes.pluginId, plugin.id)));
  } else {
    // Insert new vote
    await db.insert(votes).values({
      userId: user.id,
      pluginId: plugin.id,
      value,
    });
  }

  // Update plugin vote_score atomically
  const delta = value - oldValue;
  if (delta !== 0) {
    await db
      .update(plugins)
      .set({ voteScore: sql`${plugins.voteScore} + ${delta}` })
      .where(eq(plugins.id, plugin.id));
  }

  // Return updated widget
  const newScore = plugin.voteScore + delta;
  const userVote = value;
  const showDownvote = c.req.header("HX-Trigger-Name") === "detail-vote";

  return c.html(voteWidget(pluginName, newScore, userVote, showDownvote));
});
```

**Step 2: Register the route in `index.ts`**

Add to imports:
```typescript
import { voteRoutes } from "./routes/votes";
```

Add before `pageRoutes` (more specific routes first):
```typescript
app.route("/", voteRoutes);
```

**Step 3: Create a placeholder vote widget** (will be fleshed out in Task 4)

Create `forge/src/views/components/vote-widget.ts`:

```typescript
// forge/src/views/components/vote-widget.ts
import { html } from "hono/html";

export function voteWidget(
  pluginName: string,
  score: number,
  userVote: number,
  showDownvote: boolean
) {
  const upActive = userVote === 1;
  const downActive = userVote === -1;
  const upValue = upActive ? 0 : 1;
  const downValue = downActive ? 0 : -1;

  return html`
    <div id="vote-${pluginName}" class="flex items-center gap-1">
      <button
        hx-post="/plugins/${pluginName}/vote"
        hx-vals='{"value":${upValue}}'
        hx-target="#vote-${pluginName}"
        hx-swap="outerHTML"
        name="detail-vote"
        class="p-1 rounded hover:bg-gray-100 ${upActive ? "text-orange-500" : "text-gray-400"}"
        title="Upvote"
      >
        ▲
      </button>
      <span class="text-sm font-medium min-w-[2ch] text-center">${score}</span>
      ${showDownvote
        ? html`
            <button
              hx-post="/plugins/${pluginName}/vote"
              hx-vals='{"value":${downValue}}'
              hx-target="#vote-${pluginName}"
              hx-swap="outerHTML"
              name="detail-vote"
              class="p-1 rounded hover:bg-gray-100 ${downActive ? "text-blue-500" : "text-gray-400"}"
              title="Downvote"
            >
              ▼
            </button>
          `
        : ""}
    </div>
  `;
}
```

**Step 4: Create directory and verify typecheck**

Run: `mkdir -p forge/src/views/components`
Run: `cd forge && bun run typecheck`
Expected: 0 errors.

**Step 5: Smoke test**

Run: `cd forge && bun run dev`
Test with curl (will get 401 since no auth cookie, but should not crash):
```bash
curl -X POST http://localhost:3000/plugins/superpowers/vote \
  -H "Content-Type: application/json" \
  -d '{"value": 1}'
```
Expected: 401 (auth required) — confirms route is registered.

**Step 6: Commit**

```bash
git add forge/src/routes/votes.ts forge/src/views/components/vote-widget.ts forge/src/index.ts
git commit -m "feat(forge): add vote route and vote widget component"
```

---

### Task 4: Vote UI on Catalogue and Detail Pages

Wire the vote widget into the existing pages.

**Files:**
- Modify: `forge/src/routes/pages.ts`

**Step 1: Add vote widget to catalogue cards**

Import the vote widget at top of `pages.ts`:

```typescript
import { voteWidget } from "../views/components/vote-widget";
import { votes } from "../db/schema";
```

Update the `pluginCard` function to accept and display vote info. The card should show an upvote-only widget (no downvote on catalogue).

Update `queryPlugins` to also fetch the current user's vote for each plugin (if authenticated). This requires a left join on the votes table when a user is present.

**Step 2: Add vote widget to detail page**

On the detail page (`GET /plugins/:name`), add the vote widget with `showDownvote: true` next to the plugin title. Query the user's existing vote for this plugin to set the active state.

**Step 3: Verify typecheck and smoke test**

Run: `cd forge && bun run typecheck`
Run: `cd forge && bun run dev`
Visit `http://localhost:3000` — catalogue cards should show upvote buttons.
Visit a plugin detail page — should show up/down vote buttons.
Log in and click vote — should update via HTMX without page reload.

**Step 4: Commit**

```bash
git add forge/src/routes/pages.ts
git commit -m "feat(forge): add vote widgets to catalogue and detail pages"
```

---

### Task 5: Comment Section Component

The comment list and forms for the detail page.

**Files:**
- Create: `forge/src/views/components/comment-section.ts`

**Step 1: Create the comment section component**

This component renders:
1. A "Add comment" form with EasyMDE-enhanced textarea
2. Top-level comments (newest first) with rendered markdown bodies
3. Replies under each top-level comment (oldest first)
4. Reply form (toggleable) for each top-level comment
5. Edit/delete buttons on own comments

```typescript
// forge/src/views/components/comment-section.ts
import { html, raw } from "hono/html";
import { renderMarkdown } from "../../lib/markdown";
import type { AppUser } from "../../types";

type CommentRow = {
  id: string;
  body: string;
  parentId: string | null;
  createdAt: Date;
  updatedAt: Date;
  userId: string;
  userEmail: string;
  userDisplayName: string | null;
};

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function commentBody(comment: CommentRow, user: AppUser | null, pluginName: string, isReply: boolean) {
  const isOwner = user?.id === comment.userId;
  const displayName = comment.userDisplayName ?? comment.userEmail.split("@")[0];
  const renderedBody = renderMarkdown(comment.body);

  return html`
    <div id="comment-${comment.id}" class="${isReply ? "ml-8 border-l-2 border-gray-200 pl-4" : ""} py-3">
      <div class="flex items-center gap-2 text-sm text-gray-500 mb-1">
        <span class="font-medium text-gray-700">${displayName}</span>
        <span>&middot;</span>
        <time>${formatDate(comment.createdAt)}</time>
        ${comment.updatedAt > comment.createdAt
          ? html`<span class="italic">(edited)</span>`
          : ""}
      </div>
      <div class="prose prose-sm max-w-none">${raw(renderedBody)}</div>
      <div class="flex gap-3 mt-2 text-sm">
        ${!isReply
          ? html`
              <button
                onclick="this.closest('[id^=comment-]').querySelector('.reply-form').classList.toggle('hidden')"
                class="text-gray-500 hover:text-gray-700"
              >
                Reply
              </button>
            `
          : ""}
        ${isOwner
          ? html`
              <button
                hx-get="/plugins/${pluginName}/comments/${comment.id}/edit"
                hx-target="#comment-${comment.id}"
                hx-swap="outerHTML"
                class="text-gray-500 hover:text-gray-700"
              >
                Edit
              </button>
              <button
                hx-delete="/plugins/${pluginName}/comments/${comment.id}"
                hx-target="#comment-${comment.id}"
                hx-swap="delete"
                hx-confirm="Delete this comment?"
                class="text-red-500 hover:text-red-700"
              >
                Delete
              </button>
            `
          : ""}
      </div>
      ${!isReply
        ? html`
            <div class="reply-form hidden mt-3">
              <form
                hx-post="/plugins/${pluginName}/comments"
                hx-target="#comment-${comment.id} .replies"
                hx-swap="beforeend"
                hx-on::after-request="this.reset(); this.closest('.reply-form').classList.add('hidden')"
              >
                <input type="hidden" name="parent_id" value="${comment.id}" />
                <textarea
                  name="body"
                  required
                  maxlength="10000"
                  rows="3"
                  placeholder="Write a reply..."
                  class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                ></textarea>
                <button
                  type="submit"
                  class="mt-2 px-4 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
                >
                  Reply
                </button>
              </form>
            </div>
          `
        : ""}
    </div>
  `;
}

export function commentSection(
  pluginName: string,
  allComments: CommentRow[],
  user: AppUser | null,
) {
  // Split into top-level and replies
  const topLevel = allComments
    .filter((c) => !c.parentId)
    .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime()); // newest first

  const repliesByParent = new Map<string, CommentRow[]>();
  for (const c of allComments.filter((c) => c.parentId)) {
    const existing = repliesByParent.get(c.parentId!) ?? [];
    existing.push(c);
    repliesByParent.set(c.parentId!, existing);
  }
  // Sort replies oldest first
  for (const replies of repliesByParent.values()) {
    replies.sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());
  }

  return html`
    <div id="comments-section" class="mb-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">
        Comments (${allComments.length})
      </h2>

      ${user
        ? html`
            <form
              hx-post="/plugins/${pluginName}/comments"
              hx-target="#comments-list"
              hx-swap="afterbegin"
              hx-on::after-request="this.reset(); if(window.easyMDE) window.easyMDE.value('');"
              class="mb-6"
            >
              <textarea
                id="new-comment"
                name="body"
                required
                maxlength="10000"
                rows="4"
                placeholder="Write a comment..."
                class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              ></textarea>
              <button
                type="submit"
                class="mt-2 px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
              >
                Comment
              </button>
            </form>
          `
        : html`
            <p class="text-sm text-gray-500 mb-6">
              <a href="/auth/login" class="text-blue-600 hover:text-blue-800">Log in</a> to leave a comment.
            </p>
          `}

      <div id="comments-list" class="divide-y divide-gray-100">
        ${topLevel.map(
          (c) => html`
            <div>
              ${commentBody(c, user, pluginName, false)}
              <div class="replies">
                ${(repliesByParent.get(c.id) ?? []).map(
                  (r) => commentBody(r, user, pluginName, true)
                )}
              </div>
            </div>
          `
        )}
      </div>

      ${topLevel.length === 0
        ? html`<p class="text-gray-500 text-sm">No comments yet. Be the first!</p>`
        : ""}
    </div>
  `;
}
```

**Step 2: Verify typecheck**

Run: `cd forge && bun run typecheck`
Expected: 0 errors.

**Step 3: Commit**

```bash
git add forge/src/views/components/comment-section.ts
git commit -m "feat(forge): add comment section component"
```

---

### Task 6: Comment Routes (CRUD)

All comment operations — create, edit, delete, and load.

**Files:**
- Create: `forge/src/routes/comments.ts`
- Modify: `forge/src/index.ts` (register route)

**Step 1: Create the comments route file**

```typescript
// forge/src/routes/comments.ts
import { Hono } from "hono";
import { eq, and } from "drizzle-orm";
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
      .select({ id: comments.id, parentId: comments.parentId, pluginId: comments.pluginId })
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
    <div id="comment-${inserted.id}" class="${isReply ? "ml-8 border-l-2 border-gray-200 pl-4" : ""} py-3">
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
    <div id="comment-${updated.id}" class="${updated.parentId ? "ml-8 border-l-2 border-gray-200 pl-4" : ""} py-3">
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
        >Edit</button>
        <button
          hx-delete="/plugins/${pluginName}/comments/${updated.id}"
          hx-target="#comment-${updated.id}"
          hx-swap="delete"
          hx-confirm="Delete this comment?"
          class="text-red-500 hover:text-red-700"
        >Delete</button>
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
    <div id="comment-${comment.id}" class="${comment.parentId ? "ml-8 border-l-2 border-gray-200 pl-4" : ""} py-3">
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
          <button type="submit" class="px-4 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700">
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
```

**Step 2: Register the route in `index.ts`**

Add to imports:
```typescript
import { commentRoutes } from "./routes/comments";
```

Add before `pageRoutes`:
```typescript
app.route("/", commentRoutes);
```

**Step 3: Verify typecheck**

Run: `cd forge && bun run typecheck`
Expected: 0 errors.

**Step 4: Commit**

```bash
git add forge/src/routes/comments.ts forge/src/index.ts
git commit -m "feat(forge): add comment routes (create, edit, delete, load)"
```

---

### Task 7: Wire Comments into Detail Page

Add the comment section to the plugin detail page.

**Files:**
- Modify: `forge/src/routes/pages.ts`

**Step 1: Import and use comment section on detail page**

In the detail page route (`GET /plugins/:name`), after loading the plugin and skills, also load comments:

```typescript
import { commentSection } from "../views/components/comment-section";
import { comments, users } from "../db/schema";
```

Add a comments query after the skills query:

```typescript
const allComments = await db
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
  .where(eq(comments.pluginId, plugin.id));
```

Add the comment section after the README section in the detail page HTML:

```typescript
${commentSection(plugin.name, allComments, user)}
```

**Step 2: Verify typecheck and smoke test**

Run: `cd forge && bun run typecheck`
Run: `cd forge && bun run dev`
Visit a plugin detail page — should see "Comments (0)" section with a comment form (if logged in) or "Log in to leave a comment" (if not).

**Step 3: Commit**

```bash
git add forge/src/routes/pages.ts
git commit -m "feat(forge): wire comment section into plugin detail page"
```

---

### Task 8: EasyMDE Integration

Add the WYSIWYG markdown editor to comment forms.

**Files:**
- Modify: `forge/src/views/layout.ts`

**Step 1: Add EasyMDE CDN links to layout**

In the `<head>` section of `layout.ts`, add:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.css" />
```

Before the closing `</body>` tag, add:

```html
<script src="https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.js"></script>
<script>
  // Initialize EasyMDE on the main comment textarea (if present)
  document.addEventListener('DOMContentLoaded', function() {
    var el = document.getElementById('new-comment');
    if (el) {
      window.easyMDE = new EasyMDE({
        element: el,
        spellChecker: false,
        status: false,
        toolbar: ['bold', 'italic', 'code', 'link', '|', 'unordered-list', 'ordered-list', '|', 'preview'],
        minHeight: '100px',
        placeholder: 'Write a comment...',
      });
    }
  });
</script>
```

**Step 2: Verify it loads**

Run: `cd forge && bun run dev`
Visit a plugin detail page while logged in — the comment textarea should be replaced by EasyMDE with a toolbar.

**Step 3: Commit**

```bash
git add forge/src/views/layout.ts
git commit -m "feat(forge): add EasyMDE WYSIWYG editor for comments"
```

---

### Task 9: Sort Options on Catalogue

Add the sort dropdown and trending calculation to the catalogue page.

**Files:**
- Modify: `forge/src/routes/pages.ts`

**Step 1: Update `queryPlugins` to accept a sort parameter**

Add a `sort` parameter to the `queryPlugins` function. Define the sort options:

```typescript
import { desc, asc, sql } from "drizzle-orm";

type SortOption = "trending" | "installed" | "voted" | "newest" | "updated";

function getSortExpression(sort: SortOption) {
  switch (sort) {
    case "trending":
      return desc(
        sql`(${plugins.voteScore} + ${plugins.installCount})::float / power(extract(epoch from now() - ${plugins.createdAt}) / 3600 + 2, 1.8)`
      );
    case "installed":
      return desc(plugins.installCount);
    case "voted":
      return desc(plugins.voteScore);
    case "newest":
      return desc(plugins.createdAt);
    case "updated":
      return desc(plugins.updatedAt);
  }
}
```

Update `queryPlugins` signature to accept `sort: SortOption` and use `getSortExpression(sort)` instead of `desc(plugins.installCount)`.

**Step 2: Add sort dropdown to catalogue page HTML**

Add a sort selector above the plugin list, inside the catalogue page and the HTMX partial:

```html
<div class="flex items-center gap-2 mb-4">
  <span class="text-sm text-gray-500">Sort by:</span>
  <select
    hx-get="/partials/plugin-list"
    hx-trigger="change"
    hx-target="#plugin-list"
    hx-include="[name=q]"
    name="sort"
    class="text-sm border rounded px-2 py-1 bg-white"
  >
    <option value="trending" ${sort === "trending" ? "selected" : ""}>Trending</option>
    <option value="installed" ${sort === "installed" ? "selected" : ""}>Most installed</option>
    <option value="voted" ${sort === "voted" ? "selected" : ""}>Highest voted</option>
    <option value="newest" ${sort === "newest" ? "selected" : ""}>Newest</option>
    <option value="updated" ${sort === "updated" ? "selected" : ""}>Recently updated</option>
  </select>
</div>
```

**Step 3: Update URL handling**

Parse `sort` from query params in both the full page and HTMX partial routes. Include `sort` in pagination links so it persists across pages.

**Step 4: Verify typecheck and smoke test**

Run: `cd forge && bun run typecheck`
Run: `cd forge && bun run dev`
Visit `http://localhost:3000` — should see sort dropdown. Changing it should reload the plugin list via HTMX. Pagination links should preserve the sort option.

**Step 5: Commit**

```bash
git add forge/src/routes/pages.ts
git commit -m "feat(forge): add sort options to catalogue (trending, installed, voted, newest, updated)"
```

---

### Task 10: Integration Testing and Polish

Final verification — test all features together, fix any issues.

**Files:**
- Potentially any of the above files for bug fixes

**Step 1: Full smoke test**

Run: `cd forge && bun run dev`

Test matrix:
1. **Unauthenticated user:**
   - [ ] Can browse catalogue, see vote scores, see sort dropdown
   - [ ] Cannot vote (click shows nothing or redirects to login)
   - [ ] Can view comments on detail page
   - [ ] Cannot post comments (sees "Log in" prompt)

2. **Authenticated user:**
   - [ ] Can upvote on catalogue card (HTMX updates score)
   - [ ] Can upvote/downvote on detail page
   - [ ] Can toggle vote off (click again)
   - [ ] Can post a comment (markdown rendered)
   - [ ] Can reply to a comment (one level only)
   - [ ] Can edit own comment
   - [ ] Can delete own comment (with confirmation)
   - [ ] Cannot edit/delete other users' comments
   - [ ] Sort options work (trending, installed, voted, newest, updated)
   - [ ] Sort persists across pagination
   - [ ] EasyMDE editor loads on comment form

3. **Rate limiting:**
   - [ ] Rapid voting (>30/min) returns 429
   - [ ] Rapid commenting (>5/min) returns 429

4. **CSRF:**
   - [ ] Cross-origin POST requests are rejected (test with curl without Origin header)

**Step 2: Run typecheck**

Run: `cd forge && bun run typecheck`
Expected: 0 errors.

**Step 3: Fix any issues found during testing**

Address bugs discovered during the smoke test.

**Step 4: Final commit**

```bash
git add -A
git commit -m "fix(forge): polish Phase 3 community features after integration testing"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | CSRF Middleware | `index.ts` |
| 2 | In-Memory Rate Limiter | `lib/rate-limit.ts` (new) |
| 3 | Vote Route + Widget | `routes/votes.ts` (new), `views/components/vote-widget.ts` (new), `index.ts` |
| 4 | Vote UI on Pages | `routes/pages.ts` |
| 5 | Comment Section Component | `views/components/comment-section.ts` (new) |
| 6 | Comment Routes (CRUD) | `routes/comments.ts` (new), `index.ts` |
| 7 | Wire Comments into Detail Page | `routes/pages.ts` |
| 8 | EasyMDE Integration | `views/layout.ts` |
| 9 | Sort Options on Catalogue | `routes/pages.ts` |
| 10 | Integration Testing + Polish | All files |
