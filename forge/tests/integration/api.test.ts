import { describe, expect, test } from "bun:test";
import { anonFetch, BASE_URL, SUPABASE_URL } from "./helpers";

describe("Telemetry API (integration)", () => {
  test("POST /api/telemetry with full CLI-shaped payload returns 204 and persists row", async () => {
    const uniquePlugin = `cli-telemetry-test-${Date.now()}`;
    const res = await anonFetch("/api/telemetry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
      },
      body: JSON.stringify({
        plugin_name: uniquePlugin,
        source: "cli",
        agents: ["claude-code", "cursor"],
        version: "2.1.0",
        cli_version: "0.5.0",
        is_ci: true,
      }),
    });
    expect(res.status).toBe(204);

    // Verify the row was persisted in install_events via Supabase REST API
    const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
    const queryRes = await fetch(
      `${SUPABASE_URL}/rest/v1/install_events?plugin_name=eq.${uniquePlugin}&order=created_at.desc&limit=1`,
      {
        headers: {
          apikey: serviceRoleKey,
          Authorization: `Bearer ${serviceRoleKey}`,
        },
      },
    );
    expect(queryRes.ok).toBe(true);
    const rows = await queryRes.json();
    expect(rows).toHaveLength(1);
    expect(rows[0].plugin_name).toBe(uniquePlugin);
    expect(rows[0].source).toBe("cli");
    expect(rows[0].agents).toEqual(["claude-code", "cursor"]);
    expect(rows[0].version).toBe("2.1.0");
    expect(rows[0].cli_version).toBe("0.5.0");
    expect(rows[0].is_ci).toBe(true);
  });

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
