import { describe, expect, test } from "bun:test";
import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import type { AppEnv } from "../src/types";

/**
 * Test the global error handler pattern from src/index.ts.
 * We replicate the handler here to test it in isolation.
 */

function createAppWithErrorHandler(): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", null);
    await next();
  });

  // Test routes that throw different errors
  app.get("/throw-401", () => {
    throw new HTTPException(401, { message: "Authentication required" });
  });
  app.get("/throw-403", () => {
    throw new HTTPException(403, { message: "Forbidden" });
  });
  app.get("/throw-login-required", () => {
    throw new Error("LOGIN_REQUIRED");
  });
  app.get("/throw-generic", () => {
    throw new Error("Something unexpected");
  });

  // Replicate the global error handler from src/index.ts
  app.onError((err, c) => {
    if (err instanceof HTTPException) {
      return err.getResponse();
    }
    if (err instanceof Error && err.message.includes("LOGIN_REQUIRED")) {
      return c.redirect("/auth/login");
    }
    return c.text("Internal Server Error", 500);
  });

  return app;
}

describe("Global error handler", () => {
  test("returns 401 for HTTPException(401), not 500", async () => {
    const app = createAppWithErrorHandler();
    const res = await app.request("/throw-401");
    expect(res.status).toBe(401);
  });

  test("returns 403 for HTTPException(403), not 500", async () => {
    const app = createAppWithErrorHandler();
    const res = await app.request("/throw-403");
    expect(res.status).toBe(403);
  });

  test("redirects to login for LOGIN_REQUIRED errors", async () => {
    const app = createAppWithErrorHandler();
    const res = await app.request("/throw-login-required", {
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/auth/login");
  });

  test("returns 500 for unexpected errors", async () => {
    const app = createAppWithErrorHandler();
    const res = await app.request("/throw-generic");
    expect(res.status).toBe(500);
  });
});
