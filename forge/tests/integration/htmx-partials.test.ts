import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("HTMX partials (integration)", () => {
  test("catalogue full page contains DOCTYPE and html tags", async () => {
    const res = await anonFetch("/");
    const html = await res.text();
    expect(html.toLowerCase()).toContain("<!doctype html>");
    expect(html).toContain("<html");
  });

  test("GET /partials/plugin-list returns partial without full page shell", async () => {
    const res = await anonFetch("/partials/plugin-list");
    expect(res.status).toBe(200);
    const html = await res.text();
    // Partial should NOT contain the document wrapper
    expect(html).not.toContain("<!DOCTYPE");
    expect(html).not.toContain("<html");
  });

  test("partial is shorter than full page (no layout wrapper)", async () => {
    const fullRes = await anonFetch("/");
    const fullHtml = await fullRes.text();

    const partialRes = await anonFetch("/partials/plugin-list");
    const partialHtml = await partialRes.text();

    expect(partialHtml.length).toBeLessThan(fullHtml.length);
  });

  test("partial with search query returns filtered content", async () => {
    const res = await anonFetch("/partials/plugin-list?q=zzz_impossible_zzz");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("No plugins found");
  });

  test("partial with sort parameter works", async () => {
    const res = await anonFetch("/partials/plugin-list?sort=newest");
    expect(res.status).toBe(200);
  });

  test("partial with pagination works", async () => {
    const res = await anonFetch("/partials/plugin-list?page=0");
    expect(res.status).toBe(200);
  });
});
