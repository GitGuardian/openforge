import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("Catalogue (integration)", () => {
  test("GET / returns 200 with HTML catalogue page", async () => {
    const res = await anonFetch("/");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("OpenForge");
  });

  test("GET / contains search input", async () => {
    const res = await anonFetch("/");
    const html = await res.text();
    expect(html).toContain("Search");
  });

  test("GET /?q=nonexistent returns 200 with no results", async () => {
    const res = await anonFetch("/?q=zzz_nonexistent_plugin_zzz");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("No plugins found");
  });

  test("GET /partials/plugin-list returns partial HTML (no full page shell)", async () => {
    const res = await anonFetch("/partials/plugin-list");
    expect(res.status).toBe(200);
    const html = await res.text();
    // Partial should not contain the full HTML document wrapper
    expect(html).not.toContain("<!DOCTYPE");
  });

  test("GET /api/marketplace.json returns valid JSON with packages array", async () => {
    const res = await anonFetch("/api/marketplace.json");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toHaveProperty("version");
    expect(data).toHaveProperty("packages");
    expect(Array.isArray(data.packages)).toBe(true);
  });

  test("GET /.well-known/skills/index.json returns valid JSON with skills array", async () => {
    const res = await anonFetch("/.well-known/skills/index.json");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toHaveProperty("version");
    expect(data).toHaveProperty("skills");
    expect(Array.isArray(data.skills)).toBe(true);
  });
});
