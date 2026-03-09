import { describe, expect, test, mock } from "bun:test";
import { Hono } from "hono";
import type { AppEnv, AppUser } from "../../src/types";
import { mockUser } from "../setup";

// ---------------------------------------------------------------------------
// Mock modules
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => {
        const result = Promise.resolve([]);
        (result as any).where = () => ({
          limit: () => Promise.resolve([]),
          orderBy: () => ({
            limit: () => ({
              offset: () => Promise.resolve([]),
            }),
          }),
          then: (resolve: (v: unknown) => unknown, reject?: (e: unknown) => unknown) =>
            Promise.resolve([]).then(resolve, reject),
        });
        (result as any).leftJoin = () => ({
          where: () => ({
            orderBy: () => ({
              limit: () => ({
                offset: () => Promise.resolve([]),
              }),
            }),
          }),
        });
        (result as any).innerJoin = () => ({
          where: () => Promise.resolve([]),
        });
        return result;
      },
    }),
  },
}));

mock.module("../../src/lib/supabase", () => ({
  supabase: { auth: { getUser: () => Promise.resolve({ data: { user: null }, error: null }) } },
}));

mock.module("../../src/views/layout", () => ({
  layout: (title: string, content: unknown, user: unknown) =>
    `<html><title>${title}</title><body>${content}</body></html>`,
}));

mock.module("../../src/views/components/vote-widget", () => ({
  voteWidget: () => `<div class="vote-widget"></div>`,
}));

mock.module("../../src/views/components/comment-section", () => ({
  commentSection: () => `<div id="comments-section"></div>`,
  commentBody: () => "<div>comment</div>",
}));

const { pageRoutes } = await import("../../src/routes/pages");

// ---------------------------------------------------------------------------
// App factory
// ---------------------------------------------------------------------------

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
// GET /submit
// ---------------------------------------------------------------------------

describe("GET /submit", () => {
  test("redirects to login if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/submit", { redirect: "manual" });
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("/auth/login");
  });

  test("returns 200 with submit form when authenticated", async () => {
    const app = createApp(mockUser());
    const res = await app.request("/submit");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Submit a Plugin");
  });

  test("form contains gitUrl input field", async () => {
    const app = createApp(mockUser());
    const res = await app.request("/submit");
    const html = await res.text();
    expect(html).toContain('name="gitUrl"');
  });

  test("form contains description textarea", async () => {
    const app = createApp(mockUser());
    const res = await app.request("/submit");
    const html = await res.text();
    expect(html).toContain('name="description"');
  });

  test("form posts to /api/submissions via HTMX", async () => {
    const app = createApp(mockUser());
    const res = await app.request("/submit");
    const html = await res.text();
    expect(html).toContain("hx-post");
    expect(html).toContain("/api/submissions");
  });
});
