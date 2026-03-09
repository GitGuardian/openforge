import { describe, expect, test } from "bun:test";
import { healthRoutes } from "../../src/routes/health";

describe("GET /health", () => {
  test("returns 200 with status ok", async () => {
    const res = await healthRoutes.request("/health");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.status).toBe("ok");
    expect(body.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  test("timestamp is a valid ISO string", async () => {
    const res = await healthRoutes.request("/health");
    const body = await res.json();
    const parsed = new Date(body.timestamp);
    expect(parsed.toISOString()).toBe(body.timestamp);
  });
});
