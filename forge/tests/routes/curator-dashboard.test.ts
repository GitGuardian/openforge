import { describe, expect, test, mock, beforeEach } from "bun:test";

// ---------------------------------------------------------------------------
// Mock state
// ---------------------------------------------------------------------------

let selectResults: unknown[][] = [];

function nextSelect(): unknown[] {
  return selectResults.shift() ?? [];
}

// ---------------------------------------------------------------------------
// Mock db module
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => {
        const rows = nextSelect();
        const result = Promise.resolve(rows);
        (result as any).where = (_cond: unknown) => {
          const filtered = nextSelect();
          const whereResult = Promise.resolve(filtered.length > 0 ? filtered : rows);
          (whereResult as any).limit = () =>
            Promise.resolve(filtered.length > 0 ? filtered : rows);
          (whereResult as any).orderBy = () => {
            const ordered = Promise.resolve(filtered.length > 0 ? filtered : rows);
            (ordered as any).limit = () =>
              Promise.resolve(filtered.length > 0 ? filtered : rows);
            return ordered;
          };
          return whereResult;
        };
        (result as any).orderBy = () => {
          const ordered = Promise.resolve(rows);
          (ordered as any).limit = () => Promise.resolve(rows);
          return ordered;
        };
        return result;
      },
    }),
  },
}));

mock.module("../../src/lib/supabase", () => ({
  supabase: {
    auth: { getUser: () => Promise.resolve({ data: { user: null }, error: null }) },
  },
}));

mock.module("../../src/lib/indexer", () => ({
  indexSubmission: () => Promise.resolve(),
  indexRegistry: () => Promise.resolve(),
}));

// Import AFTER mocking
const { pageRoutes } = await import("../../src/routes/pages");

import { Hono } from "hono";
import type { AppEnv, AppUser } from "../../src/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const testUser: AppUser = {
  id: "user-001",
  email: "test@example.com",
  role: "user",
  displayName: "Test User",
  authId: "auth-001",
};

const testCurator: AppUser = {
  id: "curator-001",
  email: "curator@example.com",
  role: "curator",
  displayName: "Curator",
  authId: "auth-002",
};

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
// Tests
// ---------------------------------------------------------------------------

describe("GET /curator/submissions", () => {
  beforeEach(() => {
    selectResults = [];
  });

  test("redirects to login if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/curator/submissions");
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("/auth/login");
  });

  test("returns 403 for regular user", async () => {
    const app = createApp(testUser);
    const res = await app.request("/curator/submissions");
    expect(res.status).toBe(403);
  });

  test("shows all submissions for curator", async () => {
    selectResults.push([
      {
        id: "sub-001",
        gitUrl: "https://github.com/owner/repo-a",
        status: "pending",
        createdAt: new Date("2026-01-15"),
        reviewNote: null,
        userId: "user-001",
        pluginId: null,
      },
      {
        id: "sub-002",
        gitUrl: "https://github.com/owner/repo-b",
        status: "approved",
        createdAt: new Date("2026-01-10"),
        reviewNote: null,
        userId: "user-002",
        pluginId: "plugin-001",
      },
    ]);
    const app = createApp(testCurator);
    const res = await app.request("/curator/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("repo-a");
    expect(html).toContain("repo-b");
  });

  test("shows filter tabs", async () => {
    selectResults.push([]);
    const app = createApp(testCurator);
    const res = await app.request("/curator/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("All");
    expect(html).toContain("Pending");
    expect(html).toContain("Approved");
    expect(html).toContain("Rejected");
  });

  test("filters by status query param", async () => {
    // First select returns all, second returns filtered pending
    selectResults.push([
      {
        id: "sub-001",
        gitUrl: "https://github.com/owner/pending-repo",
        status: "pending",
        createdAt: new Date("2026-01-15"),
        reviewNote: null,
        userId: "user-001",
        pluginId: null,
      },
    ]);
    const app = createApp(testCurator);
    const res = await app.request("/curator/submissions?status=pending");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("pending-repo");
  });

  test("shows empty state when no submissions", async () => {
    selectResults.push([]);
    const app = createApp(testCurator);
    const res = await app.request("/curator/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("No submissions");
  });

  test("shows approve/reject buttons for pending submissions", async () => {
    selectResults.push([
      {
        id: "sub-001",
        gitUrl: "https://github.com/owner/pending-repo",
        status: "pending",
        createdAt: new Date("2026-01-15"),
        reviewNote: null,
        userId: "user-001",
        pluginId: null,
      },
    ]);
    const app = createApp(testCurator);
    const res = await app.request("/curator/submissions?status=pending");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Approve");
    expect(html).toContain("Reject");
    expect(html).toContain("hx-post");
    expect(html).toContain("/api/submissions/sub-001/review");
  });

  test("does not show action buttons for approved submissions", async () => {
    selectResults.push([
      {
        id: "sub-002",
        gitUrl: "https://github.com/owner/approved-repo",
        status: "approved",
        createdAt: new Date("2026-01-10"),
        reviewNote: null,
        userId: "user-001",
        pluginId: null,
      },
    ]);
    const app = createApp(testCurator);
    const res = await app.request("/curator/submissions?status=approved");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).not.toContain("hx-post");
  });

  test("admin can access curator dashboard", async () => {
    const testAdmin: AppUser = {
      id: "admin-001",
      email: "admin@example.com",
      role: "admin",
      displayName: "Admin",
      authId: "auth-003",
    };
    selectResults.push([]);
    const app = createApp(testAdmin);
    const res = await app.request("/curator/submissions");
    expect(res.status).toBe(200);
  });
});
