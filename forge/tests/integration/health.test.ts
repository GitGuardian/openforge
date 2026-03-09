import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("Health (integration)", () => {
  test("GET /health returns 200 with ok status", async () => {
    const res = await anonFetch("/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  test("GET /health returns JSON content type", async () => {
    const res = await anonFetch("/health");
    expect(res.headers.get("content-type")).toContain("application/json");
  });
});
