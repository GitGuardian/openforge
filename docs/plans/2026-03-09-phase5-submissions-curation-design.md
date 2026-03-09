# Phase 5: Submissions & Curation — Design

## Overview

Add a community submission pipeline and curator review workflow to OpenForge. Users submit plugins via the Forge UI or CLI, curators review and approve/reject, and approved plugins appear in the catalogue.

Existing webhook auto-indexing (Phase 4) is unchanged — it remains the trusted path with auto-approval. Submissions are the untrusted path requiring review.

## Decisions

- **Both submissions and curator tools** in one phase
- **Two entry points:** Forge UI form + CLI `openforge publish`
- **Inline review first** (steel thread), full curator dashboard later in phase
- **Webhook auto-indexing unchanged** — trusted path stays auto-approved
- **Authentication required** to submit
- **TDD red/green** for all implementation
- **Steel thread first** — thinnest end-to-end path, then widen

---

## Data Model

### New status values on `plugins` table

Current: `approved` (default for webhook-indexed). Add: `pending`, `rejected`.

### New `submissions` table

| Column     | Type      | Notes                                    |
|------------|-----------|------------------------------------------|
| id         | uuid PK   |                                          |
| pluginId   | uuid FK → plugins | nullable until indexing completes |
| userId     | uuid FK → users   | the submitter                    |
| gitUrl     | text      | required — repo URL                      |
| description| text      | optional submitter notes                 |
| status     | enum      | `pending`, `approved`, `rejected`        |
| reviewerId | uuid FK → users   | nullable — curator who reviewed  |
| reviewNote | text      | nullable — reason for rejection          |
| createdAt  | timestamp |                                          |
| reviewedAt | timestamp | nullable                                 |

**Why a separate table?** Keeps submission metadata (who submitted, review history, rejection reasons) separate from the plugin catalogue. A plugin only enters the `plugins` table once indexing succeeds. The `submissions` table is the audit trail.

### RLS Policies

- Submitters see their own submissions
- Curators/admins see all submissions
- Regular users see nothing in `submissions` (they only see approved plugins in catalogue)

---

## API

### `POST /api/submissions` (authenticated)

- Body: `{ gitUrl: string, description?: string }`
- Validates URL format (GitHub/GitLab)
- Creates submission with status `pending`
- Kicks off async indexing (reuses Phase 4 indexer) to validate plugin structure
- If indexing succeeds: creates plugin record with `status: 'pending'`, links `pluginId`
- If indexing fails: marks submission as `rejected` with `reviewNote: "Invalid plugin structure: <reason>"`
- Returns `{ id, status }`

### `GET /api/submissions` (authenticated)

- Submitters: returns their own submissions
- Curators/admins: returns all, filterable by status
- Includes linked plugin preview data (name, description)

### `POST /api/submissions/:id/review` (curator/admin only)

- Body: `{ action: 'approve' | 'reject', note?: string }`
- Approve: sets submission + plugin status to `approved`
- Reject: sets submission + plugin status to `rejected`, stores note

---

## CLI Entry Point

### `openforge publish <git-url> [--description "..."]`

- Authenticates against Forge (stored token or interactive login)
- POSTs to `/api/submissions`
- Shows submission status and link to view on Forge

---

## Forge UI

### Submit page (`/submit`, authenticated)

- Simple form: git URL (required) + description (optional)
- POSTs to `/api/submissions` via HTMX
- Shows confirmation with link to track status

### Inline curator review (steel thread)

- On plugin detail page, when curator views a `pending` plugin:
  - Banner: "This plugin is pending review" with submitter info
  - Approve / Reject buttons (reject shows note input)
  - Full plugin detail visible for in-place review
- POSTs to `/api/submissions/:id/review` via HTMX

### Curator dashboard (`/curator/submissions`, later in phase)

- Table: plugin name, submitter, submitted date, status
- Filter by status, sort by date
- Click through to plugin detail for review
- Pending count badge in nav bar for curators

### Submitter status page (`/my/submissions`)

- List of user's own submissions with status
- Rejection reason visible if rejected
- Link to resubmit (creates a new submission)

---

## Implementation Sequence (Steel Thread First)

### Steel thread (tasks 1-3)

1. **DB + API** — `submissions` table, migration, RLS policies, `POST /api/submissions` endpoint (without async indexing — just stores the submission)
2. **Forge UI submit form** — `/submit` page with git URL field, posts to API, shows confirmation
3. **Inline curator review** — Approve/reject buttons on plugin detail page for curators, `POST /api/submissions/:id/review`

At this point: user submits URL → curator approves/rejects → approved plugin appears in catalogue.

### Widen (tasks 4-8)

4. **Async indexing on submit** — Reuse Phase 4 indexer to validate plugin structure and extract metadata
5. **CLI `openforge publish`** — New command hitting same API, including auth token flow
6. **Submitter status page** — `/my/submissions` with own submissions and status
7. **Curator dashboard** — `/curator/submissions` with table, filters, pending count badge
8. **Notifications** — Email or in-app notification to submitter on approve/reject

### TDD and test coverage

Each task uses red/green TDD. Tests cover not just the happy path but:

- **Validation:** invalid URLs, duplicate submissions for same repo, submitting already-approved repo
- **Auth:** unauthenticated access blocked, submitter can't review, regular user can't see pending plugins
- **RLS:** submitter only sees own submissions, curator sees all, regular user sees nothing
- **Indexing failures:** invalid repo, no plugin structure, private repo, timeout
- **Review edge cases:** reviewing already-reviewed submission, approving when indexing failed, concurrent reviews
- **CLI:** auth failures, network errors, invalid input, server error responses
