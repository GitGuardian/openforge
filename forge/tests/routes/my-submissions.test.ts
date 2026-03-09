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
        (result as any).where = () => {
          const whereResult = Promise.resolve(rows);
          (whereResult as any).limit = () => Promise.resolve(rows);
          return whereResult;
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

describe("GET /my/submissions", () => {
  beforeEach(() => {
    selectResults = [];
  });

  test("redirects to login if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/my/submissions");
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("/auth/login");
  });

  test("shows empty state when user has no submissions", async () => {
    selectResults.push([]); // no submissions
    const app = createApp(testUser);
    const res = await app.request("/my/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("no submissions");
  });

  test("shows submission with pending status badge", async () => {
    selectResults.push([
      {
        id: "sub-001",
        gitUrl: "https://github.com/owner/repo",
        status: "pending",
        createdAt: new Date("2026-01-15"),
        reviewNote: null,
        pluginId: null,
      },
    ]);
    const app = createApp(testUser);
    const res = await app.request("/my/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("github.com/owner/repo");
    expect(html).toContain("pending");
  });

  test("shows approved status badge", async () => {
    selectResults.push([
      {
        id: "sub-002",
        gitUrl: "https://github.com/owner/approved-repo",
        status: "approved",
        createdAt: new Date("2026-01-10"),
        reviewNote: null,
        pluginId: "plugin-001",
      },
    ]);
    const app = createApp(testUser);
    const res = await app.request("/my/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("approved");
  });

  test("shows rejected status with rejection note", async () => {
    selectResults.push([
      {
        id: "sub-003",
        gitUrl: "https://github.com/owner/rejected-repo",
        status: "rejected",
        createdAt: new Date("2026-01-12"),
        reviewNote: "Missing plugin.json",
        pluginId: null,
      },
    ]);
    const app = createApp(testUser);
    const res = await app.request("/my/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("rejected");
    expect(html).toContain("Missing plugin.json");
  });

  test("renders page title My Submissions", async () => {
    selectResults.push([]);
    const app = createApp(testUser);
    const res = await app.request("/my/submissions");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("My Submissions");
  });
});
