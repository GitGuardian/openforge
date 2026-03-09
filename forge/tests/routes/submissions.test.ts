import { describe, expect, test, mock, beforeEach } from "bun:test";

// ---------------------------------------------------------------------------
// Mock state — queues for multi-step DB operations
// ---------------------------------------------------------------------------

let lastInsertValues: Record<string, unknown> | null = null;
let selectResults: unknown[][] = [];
let updateResults: unknown[][] = [];
let lastUpdateSetValues: Record<string, unknown> | null = null;

function nextSelect(): unknown[] {
  return selectResults.shift() ?? [];
}

function nextUpdate(): unknown[] {
  return updateResults.shift() ?? [];
}

// ---------------------------------------------------------------------------
// Mock db module — chainable builder matching Drizzle patterns
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    insert: (_table: unknown) => ({
      values: (values: Record<string, unknown>) => {
        lastInsertValues = values;
        return {
          returning: () =>
            Promise.resolve([
              {
                id: "sub-001",
                userId: values.userId,
                gitUrl: values.gitUrl,
                description: values.description ?? null,
                status: values.status ?? "pending",
                createdAt: new Date().toISOString(),
              },
            ]),
        };
      },
    }),
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
    update: (_table: unknown) => ({
      set: (values: Record<string, unknown>) => {
        lastUpdateSetValues = values;
        return {
          where: () => {
            const rows = nextUpdate();
            const result = Promise.resolve(rows);
            (result as any).returning = () => Promise.resolve(rows);
            return result;
          },
        };
      },
    }),
  },
}));

mock.module("../../src/lib/supabase", () => ({
  supabase: {
    auth: { getUser: () => Promise.resolve({ data: { user: null }, error: null }) },
  },
}));

let indexSubmissionCalled: string | null = null;
let indexSubmissionResult: { pluginsFound: number; errors: string[] } = {
  pluginsFound: 1,
  errors: [],
};

mock.module("../../src/lib/indexer", () => ({
  indexSubmission: async (submissionId: string) => {
    indexSubmissionCalled = submissionId;
    return indexSubmissionResult;
  },
}));

mock.module("../../src/lib/notifications", () => ({
  notifySubmissionReviewed: () => Promise.resolve(),
}));

const { submissionRoutes } = await import("../../src/routes/submissions");

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
  app.route("/", submissionRoutes);
  return app;
}

// ---------------------------------------------------------------------------
// POST /api/submissions
// ---------------------------------------------------------------------------

describe("POST /api/submissions", () => {
  beforeEach(() => {
    lastInsertValues = null;
    selectResults = [];
    updateResults = [];
    lastUpdateSetValues = null;
    indexSubmissionCalled = null;
    indexSubmissionResult = { pluginsFound: 1, errors: [] };
  });

  test("returns 401 if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
    });
    expect(res.status).toBe(401);
  });

  test("returns 400 if gitUrl is missing", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
  });

  test("returns 400 if gitUrl is invalid", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "not-a-url" }),
    });
    expect(res.status).toBe(400);
  });

  test("returns 400 if gitUrl is not GitHub or GitLab", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://bitbucket.org/owner/repo" }),
    });
    expect(res.status).toBe(400);
  });

  test("creates submission and returns 201 with pending status", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
    });
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.id).toBe("sub-001");
    expect(body.status).toBe("pending");
    expect(body.gitUrl).toBe("https://github.com/owner/repo");
  });

  test("accepts GitLab URLs", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://gitlab.com/owner/repo" }),
    });
    expect(res.status).toBe(201);
  });

  test("accepts .git suffix in URL", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo.git" }),
    });
    expect(res.status).toBe(201);
  });

  test("stores userId from authenticated user", async () => {
    const app = createApp(testUser);
    await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
    });
    expect(lastInsertValues).not.toBeNull();
    expect(lastInsertValues!.userId).toBe("user-001");
  });

  test("returns 400 for invalid JSON body", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "not json",
    });
    expect(res.status).toBe(400);
  });

  test("returns 409 if gitUrl already has a pending submission", async () => {
    // First select: duplicate check finds existing pending submission
    selectResults.push([{ id: "existing-sub", gitUrl: "https://github.com/owner/repo", status: "pending" }]);
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
    });
    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.error).toContain("already");
  });

  test("triggers background indexing after successful submission", async () => {
    // Empty select: no duplicate
    selectResults.push([]);
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
    });
    expect(res.status).toBe(201);
    // Give background task a tick to fire
    await new Promise((r) => setTimeout(r, 10));
    expect(indexSubmissionCalled).toBe("sub-001");
  });
});

// ---------------------------------------------------------------------------
// GET /api/submissions
// ---------------------------------------------------------------------------

describe("GET /api/submissions", () => {
  beforeEach(() => {
    selectResults = [];
    updateResults = [];
  });

  test("returns 401 if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/api/submissions");
    expect(res.status).toBe(401);
  });

  test("returns submissions for authenticated user", async () => {
    selectResults.push([
      { id: "sub-001", userId: "user-001", gitUrl: "https://github.com/a/b", status: "pending" },
    ]);
    const app = createApp(testUser);
    const res = await app.request("/api/submissions");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toBeArray();
    expect(body).toHaveLength(1);
    expect(body[0].id).toBe("sub-001");
  });

  test("returns all submissions for curator", async () => {
    selectResults.push([
      { id: "sub-001", userId: "user-001", status: "pending" },
      { id: "sub-002", userId: "user-002", status: "approved" },
    ]);
    const app = createApp(testCurator);
    const res = await app.request("/api/submissions");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toHaveLength(2);
  });

  test("returns empty array when no submissions exist", async () => {
    selectResults.push([]);
    const app = createApp(testUser);
    const res = await app.request("/api/submissions");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// POST /api/submissions/:id/review
// ---------------------------------------------------------------------------

describe("POST /api/submissions/:id/review", () => {
  beforeEach(() => {
    selectResults = [];
    updateResults = [];
    lastUpdateSetValues = null;
  });

  test("returns 401 if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(401);
  });

  test("returns 403 if user is not curator or admin", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(403);
  });

  test("returns 400 if action is missing", async () => {
    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
  });

  test("returns 400 if action is invalid", async () => {
    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "maybe" }),
    });
    expect(res.status).toBe(400);
  });

  test("returns 404 if submission not found", async () => {
    selectResults.push([]); // empty — no submission found
    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/nonexistent/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(404);
  });

  test("returns 409 if submission already reviewed", async () => {
    selectResults.push([{ id: "sub-001", status: "approved", pluginId: null }]);
    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(409);
  });

  test("approves a pending submission and returns 200", async () => {
    selectResults.push([{ id: "sub-001", status: "pending", pluginId: "plugin-001" }]);
    updateResults.push([{ id: "sub-001", status: "approved" }]); // submission update
    updateResults.push([]); // plugin status update (no returning)

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe("sub-001");
    expect(body.status).toBe("approved");
  });

  test("rejects a pending submission with note", async () => {
    selectResults.push([{ id: "sub-001", status: "pending", pluginId: "plugin-001" }]);
    updateResults.push([{ id: "sub-001", status: "rejected" }]);
    updateResults.push([]);

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "reject", note: "Missing README" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe("sub-001");
    expect(body.status).toBe("rejected");
  });

  test("approves submission without linked plugin (no plugin update)", async () => {
    selectResults.push([{ id: "sub-001", status: "pending", pluginId: null }]);
    updateResults.push([{ id: "sub-001", status: "approved" }]);

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("approved");
  });

  test("admin can also review submissions", async () => {
    const testAdmin: AppUser = {
      id: "admin-001",
      email: "admin@example.com",
      role: "admin",
      displayName: "Admin",
      authId: "auth-003",
    };
    selectResults.push([{ id: "sub-001", status: "pending", pluginId: null }]);
    updateResults.push([{ id: "sub-001", status: "approved" }]);

    const app = createApp(testAdmin);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(200);
  });

  test("returns HTML partial when HX-Request header is present (approve)", async () => {
    selectResults.push([{ id: "sub-001", status: "pending", pluginId: null }]);
    updateResults.push([{ id: "sub-001", status: "approved" }]);

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "HX-Request": "true",
      },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("approved");
    expect(res.headers.get("content-type")).toContain("text/html");
  });

  test("returns HTML partial when HX-Request header is present (reject)", async () => {
    selectResults.push([{ id: "sub-001", status: "pending", pluginId: null }]);
    updateResults.push([{ id: "sub-001", status: "rejected" }]);

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-001/review", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "HX-Request": "true",
      },
      body: JSON.stringify({ action: "reject", note: "No README" }),
    });
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("rejected");
    expect(res.headers.get("content-type")).toContain("text/html");
  });
});
