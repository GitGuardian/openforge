# Phase 3: Community Features — Design Document

**Date:** 2026-03-08
**Status:** Approved
**Depends on:** Phase 2 (The Forge MVP) — complete
**Goal:** Make The Forge interactive — users can vote on plugins, discuss them in threaded comments, and sort by multiple criteria including trending.

---

## Scope

| In scope | Out of scope (later phases) |
|----------|---------------------------|
| Upvote/downvote on plugins (HN-style) | Comment voting |
| Configurable downvote policy | Full rate limiting (Phase 6) |
| Threaded comments (one-level nesting) | Security headers (Phase 6) |
| Markdown comments with WYSIWYG editor | Webhook-driven indexing (Phase 4) |
| Sort options (trending, installed, voted, newest, updated) | Admin settings UI (Phase 5+) |
| CSRF protection | Notifications (Phase 5) |
| Inline input validation and rate limiting | |

---

## Existing Foundation

Phase 2 already provides:

- **`votes` table** — composite PK `(user_id, plugin_id)`, `value smallint CHECK (value IN (-1, 1))`. RLS: own votes only.
- **`comments` table** — `parent_id` for nesting, `body` text. RLS: public read, own write/edit/delete.
- **`plugins.vote_score`** — integer column, default 0.
- **Auth middleware** — `requireAuth()`, `requireRole()`, `requireAuthOrRedirect()` helpers.
- **Markdown pipeline** — `marked` + `dompurify` for server-side rendering with XSS prevention.
- **HTMX partials pattern** — already used for catalogue search (`/partials/plugin-list`).

No schema changes required. All tables and RLS policies are in place.

---

## Voting System

### UX: HN-Style

- **Catalogue cards:** Upvote button only. Shows net score. Click toggles upvote on/off.
- **Detail page:** Both upvote and downvote buttons. Active state shown for current user's vote.
- **Downvote gating:** Configurable policy (see below). Upvoting is always available to authenticated users.

### Downvote Policy

Admin-configurable setting controlling who can downvote:

| Policy | Behavior | Use case |
|--------|----------|----------|
| `authenticated` | Any logged-in user can downvote | Private/internal deployments (trusted users) |
| `karma:N` | User must have received N total upvotes on their own plugins before downvoting | Public deployments (earned privilege) |

**Default:** `authenticated` when `OPENFORGE_MODE=private`, `karma:10` when `OPENFORGE_MODE=public`.

**Configuration:** `DOWNVOTE_POLICY` env var. Format: `authenticated` or `karma:10`. Future: admin settings table in the database.

### Vote Mechanics

- One vote per user per plugin. Changing from upvote to downvote replaces the existing vote (upsert on composite PK).
- Value `0` means remove vote (delete the row).
- On vote change, compute the delta and update `plugins.vote_score` atomically:
  ```sql
  UPDATE plugins SET vote_score = vote_score + :delta WHERE id = :plugin_id
  ```
- Delta calculation: `new_value - old_value` (where old_value is 0 if no prior vote).

### Route

```
POST /plugins/:name/vote
```

- **Auth:** Required.
- **Body:** `{ "value": 1 | -1 | 0 }`
- **Validation:** value must be -1, 0, or 1. Downvote (-1) checked against downvote policy.
- **Response:** HTMX partial — updated vote buttons + score. Uses `hx-swap="outerHTML"` to replace the vote widget.
- **Error:** 401 if not authenticated, 403 if downvote not allowed by policy, 400 if invalid value.

### Vote Widget (HTMX)

On catalogue cards:
```html
<div id="vote-{plugin-name}" class="flex items-center gap-2">
  <button hx-post="/plugins/{name}/vote" hx-vals='{"value":1}' hx-target="#vote-{name}" hx-swap="outerHTML"
    class="{active ? 'text-orange-500' : 'text-gray-400'}">▲</button>
  <span class="text-sm font-medium">{score}</span>
</div>
```

On detail page — same pattern with an additional downvote button (conditionally rendered based on policy).

---

## Comments System

### UX

- Comments section on the **detail page**, below the README.
- **One-level nesting:** top-level comments + direct replies. No reply-to-reply.
- Each top-level comment has a "Reply" button that expands an inline reply form.
- Users can **edit** and **delete** their own comments.
- Delete requires confirmation via `hx-confirm`.

### Comment Editor

- **EasyMDE** loaded from CDN (`https://cdn.jsdelivr.net/npm/easymde/dist/easymde.min.js` + CSS).
- Enhances the comment `<textarea>` with a toolbar (bold, italic, code, link, preview).
- Outputs raw markdown — stored in `comments.body`.
- On display, markdown rendered with `marked` + `dompurify` (same pipeline as READMEs).

### Ordering

- Top-level comments: **newest first** (encourages fresh discussion).
- Replies within a thread: **oldest first** (chronological conversation flow).

### Routes

```
POST   /plugins/:name/comments      — Create comment
GET    /plugins/:name/comments      — Load comments (HTMX partial)
PATCH  /plugins/:name/comments/:id  — Edit own comment
DELETE /plugins/:name/comments/:id  — Delete own comment
```

**Create comment:**
- Auth required.
- Body: `{ "body": "markdown text", "parent_id": "uuid" | null }`
- `parent_id` must reference a top-level comment (one with `parent_id = null`). If the referenced comment itself has a `parent_id`, reject with 400 — enforces one-level max.
- Returns HTMX partial inserting the new comment into the list.

**Edit comment:**
- Auth required + ownership check (`comment.user_id == current_user.id`).
- Body: `{ "body": "updated markdown" }`
- Returns updated comment partial.

**Delete comment:**
- Auth required + ownership check.
- Returns empty response with `HX-Trigger: commentDeleted` for client-side removal, or use `hx-swap="delete"` on the button.

**Load comments:**
- No auth required (public read per RLS).
- Returns full comments section as HTMX partial.
- Used for initial load on detail page (`hx-get` on page load or inline).

### Input Validation

- Max body length: **10,000 characters** (reject longer with 400).
- Body must not be empty after trimming whitespace.
- DOMPurify sanitizes all rendered output.
- `parent_id` if provided must be a valid UUID referencing an existing top-level comment on the same plugin.

---

## Sorting & Ranking

### Sort Options

Dropdown/pill bar on the catalogue page, above the plugin list:

| Option | Sort expression | Description |
|--------|----------------|-------------|
| **Trending** (default) | `(vote_score + install_count) / (age_hours + 2) ^ 1.8` | HN-style, surfaces recently popular |
| **Most installed** | `install_count DESC` | Current default |
| **Highest voted** | `vote_score DESC` | Community signal |
| **Newest** | `created_at DESC` | Latest additions |
| **Recently updated** | `updated_at DESC` | Recently refreshed |

### Implementation

- Sort selection via query parameter: `?sort=trending` (default if omitted).
- HTMX: dropdown triggers `hx-get="/partials/plugin-list?sort=trending&q=..."` with `hx-target="#plugin-list"`.
- Sort persists in URL — survives pagination and is shareable/bookmarkable.

### Trending SQL

Computed at query time — no materialized column needed at our scale:

```sql
(vote_score + install_count)::float
  / power(extract(epoch from now() - created_at) / 3600 + 2, 1.8)
DESC
```

### UI

Pill-style toggle bar or small `<select>` dropdown. Minimal — not a full filter panel. Active sort option is visually highlighted.

---

## CSRF & Inline Hardening

### CSRF Protection

- Hono built-in `csrf()` middleware added in `index.ts` before route registration.
- Validates `Origin` header on POST/PATCH/DELETE requests. HTMX sends `Origin` automatically.
- Auth cookies set with `SameSite=Lax` (belt-and-suspenders).

### Input Validation Summary

| Input | Validation |
|-------|-----------|
| Vote value | Must be -1, 0, or 1. Downvote checked against policy. |
| Comment body | Max 10,000 chars. Non-empty after trim. Rendered through DOMPurify. |
| Comment parent_id | Must be valid UUID, must reference top-level comment on same plugin. |
| Plugin name (URL param) | Already validated by Drizzle query (no match = 404). |

### Inline Rate Limiting

Simple in-memory rate check (replaced by proper rate limiting in Phase 6):

- **Comments:** Max 5 per user per minute.
- **Votes:** Max 30 per user per minute.
- Implementation: `Map<string, number[]>` keyed by user ID, storing timestamps. Pruned on each check.
- Resets on server restart — acceptable for local dev.

---

## New Dependencies

| Dependency | Type | Purpose |
|-----------|------|---------|
| EasyMDE | CDN (`<script>` + `<link>`) | WYSIWYG markdown editor for comments |

No new npm packages. EasyMDE loaded from CDN like Tailwind and HTMX.

---

## File Changes

### New files
- `forge/src/routes/votes.ts` — Vote route handler
- `forge/src/routes/comments.ts` — Comment route handlers (CRUD)
- `forge/src/views/components/vote-widget.ts` — Vote button HTMX partial
- `forge/src/views/components/comment-section.ts` — Comments list + forms
- `forge/src/lib/rate-limit.ts` — Simple in-memory rate limiter

### Modified files
- `forge/src/index.ts` — Register new routes, add CSRF middleware
- `forge/src/routes/pages.ts` — Add sort parameter to catalogue query, update detail page to include vote widget and comments section
- `forge/src/views/layout.ts` — Add EasyMDE CDN link/script
- `forge/src/views/components/plugin-card.ts` (inline in pages.ts currently) — Add upvote button to cards

### No schema changes
All tables (`votes`, `comments`, `plugins.vote_score`) already exist with correct structure and RLS policies.

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| XSS via comment markdown | DOMPurify sanitization on rendered output |
| CSRF on vote/comment POST | Hono `csrf()` middleware validating Origin header |
| Comment spam | In-memory rate limit (5/min/user), replaced by proper limiter in Phase 6 |
| Vote manipulation | One vote per user per plugin (DB constraint), rate limit (30/min/user) |
| Deep nesting abuse | Server-side enforcement: reject parent_id pointing to a reply |
| Drive-by downvotes | Downvotes only on detail page, configurable karma threshold |
| Oversized comments | 10,000 char server-side limit |
