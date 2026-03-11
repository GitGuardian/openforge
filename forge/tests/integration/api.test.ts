import { describe, expect, test } from "bun:test";
import { anonFetch, BASE_URL } from "./helpers";

describe("Telemetry API (integration)", () => {
  test("POST /api/telemetry with valid body returns 204", async () => {
    const res = await anonFetch("/api/telemetry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
      },
      body: JSON.stringify({
        plugin_name: "test-plugin",
        source: "cli",
        agents: ["claude-code"],
        version: "1.0.0",
      }),
    });
    expect(res.status).toBe(204);
  });

  test("POST /api/telemetry with invalid plugin_name returns 400", async () => {
    const res = await anonFetch("/api/telemetry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
      },
      body: JSON.stringify({
        plugin_name: "",
        source: "cli",
      }),
    });
    expect(res.status).toBe(400);
  });

  test("POST /api/telemetry with invalid source returns 400", async () => {
    const res = await anonFetch("/api/telemetry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
      },
      body: JSON.stringify({
        plugin_name: "test-plugin",
        source: "unknown-source",
      }),
    });
    expect(res.status).toBe(400);
  });

  test("POST /api/telemetry with oversized body returns 413", async () => {
    const res = await anonFetch("/api/telemetry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": "5000",
        Origin: BASE_URL,
      },
      body: JSON.stringify({
        plugin_name: "test-plugin",
        source: "cli",
        data: "x".repeat(5000),
      }),
    });
    // Should be 413 (payload too large) or 400
    expect(res.status).toBeGreaterThanOrEqual(400);
    expect(res.status).toBeLessThan(500);
  });
});
