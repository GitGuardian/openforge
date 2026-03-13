import { describe, expect, test, mock } from "bun:test";

/**
 * Integration test verifying submissions API is accessible without CSRF tokens.
 * The submissions routes are registered before CSRF middleware in index.ts,
 * so CLI/API clients using Bearer auth can call them without a CSRF token.
 */

// ---------------------------------------------------------------------------
// Mock modules
// ---------------------------------------------------------------------------

const mockUser = {
  id: "user-001",
  email: "test@example.com",
  displayName: "Test",
  role: "user",
  authId: "auth-001",
};

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => {
        const result = Promise.resolve([]);
        (result as any).where = () => {
          const wr = Promise.resolve([]);
          (wr as any).limit = () => Promise.resolve([]);
          return wr;
        };
        return result;
      },
    }),
    insert: () => ({
      values: (v: any) => ({
        returning: () =>
          Promise.resolve([
            { id: "sub-001", userId: v.userId, gitUrl: v.gitUrl, status: "pending" },
          ]),
      }),
    }),
    update: () => ({
      set: () => ({
        where: () => Promise.resolve(),
      }),
    }),
  },
}));

mock.module("../../src/lib/supabase", () => ({
  supabase: {
    auth: {
      getUser: (token: string) => {
        if (token === "valid-bearer-token") {
          return Promise.resolve({
            data: { user: { id: "auth-001", email: "test@example.com" } },
            error: null,
          });
        }
        return Promise.resolve({ data: { user: null }, error: { message: "bad" } });
      },
    },
  },
}));

mock.module("../../src/lib/indexer", () => ({
  indexSubmission: () => Promise.resolve(),
  indexRegistry: () => Promise.resolve(),
}));

mock.module("../../src/lib/notifications", () => ({
  notifySubmissionReviewed: () => Promise.resolve(),
}));

// Import the full app (index.ts) to test real middleware ordering
const app = (await import("../../src/index")).default;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Submissions API — CSRF enforcement on cookie auth", () => {
  test("POST /api/submissions from cross-origin form submission returns 403", async () => {
    const res = await app.fetch(
      new Request("http://localhost/api/submissions", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          Origin: "https://evil.com",
        },
        body: "gitUrl=https%3A%2F%2Fgithub.com%2Fowner%2Frepo",
      }),
    );
    expect(res.status).toBe(403);
  });

  test("POST /api/submissions/:id/review from cross-origin form submission returns 403", async () => {
    const res = await app.fetch(
      new Request("http://localhost/api/submissions/00000000-0000-0000-0000-000000000001/review", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          Origin: "https://evil.com",
        },
        body: "action=approve",
      }),
    );
    expect(res.status).toBe(403);
  });
});

describe("Submissions API — CSRF bypass for Bearer auth", () => {
  test("POST /api/submissions succeeds with Bearer token and no CSRF token", async () => {
    const res = await app.fetch(
      new Request("http://localhost/api/submissions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer valid-bearer-token",
        },
        body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
      }),
    );
    // Should get 201 (created) or 401 (auth issue), but NOT 403 (CSRF rejection)
    expect(res.status).not.toBe(403);
  });

  test("GET /api/submissions succeeds with Bearer token and no CSRF token", async () => {
    const res = await app.fetch(
      new Request("http://localhost/api/submissions", {
        method: "GET",
        headers: {
          Authorization: "Bearer valid-bearer-token",
        },
      }),
    );
    expect(res.status).not.toBe(403);
  });
});
