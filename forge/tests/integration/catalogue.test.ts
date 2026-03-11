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

  test("GET /?page=1 returns 200 without error", async () => {
    // page param is 0-indexed; page=1 is the second page
    const res = await anonFetch("/?page=1");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).not.toContain("Internal Server Error");
  });

  test("page 0 and page 1 differ (page 1 has fewer plugins)", async () => {
    // page param is 0-indexed; with <20 seeded plugins, page 1 should be empty
    const [page0Res, page1Res] = await Promise.all([
      anonFetch("/?page=0"),
      anonFetch("/?page=1"),
    ]);
    const page0 = await page0Res.text();
    const page1 = await page1Res.text();
    const page0Cards = (page0.match(/href="\/plugins\//g) || []).length;
    const page1Cards = (page1.match(/href="\/plugins\//g) || []).length;
    expect(page0Cards).toBeGreaterThan(0);
    expect(page1Cards).toBeLessThan(page0Cards);
  });

  test("GET /?page=-1 clamps to page 0 (no error)", async () => {
    const res = await anonFetch("/?page=-1");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).not.toContain("Internal Server Error");
  });

  test("GET /?page=999 returns 200 with no plugins", async () => {
    const res = await anonFetch("/?page=999");
    expect(res.status).toBe(200);
    const html = await res.text();
    const cards = (html.match(/href="\/plugins\//g) || []).length;
    expect(cards).toBe(0);
  });
});
