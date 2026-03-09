import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("Search (integration)", () => {
  test("GET /?q=<term> returns filtered results", async () => {
    const res = await anonFetch("/?q=test");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("OpenForge");
  });

  test("GET /?q=nonexistent returns no results message", async () => {
    const res = await anonFetch("/?q=zzz_impossible_query_zzz");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("No plugins found");
  });

  test("GET /?sort=newest returns sorted results", async () => {
    const res = await anonFetch("/?sort=newest");
    expect(res.status).toBe(200);
  });

  test("GET /?sort=most_installed returns sorted results", async () => {
    const res = await anonFetch("/?sort=most_installed");
    expect(res.status).toBe(200);
  });

  test("GET /?sort=highest_voted returns sorted results", async () => {
    const res = await anonFetch("/?sort=highest_voted");
    expect(res.status).toBe(200);
  });

  test("GET /?sort=recently_updated returns sorted results", async () => {
    const res = await anonFetch("/?sort=recently_updated");
    expect(res.status).toBe(200);
  });

  test("GET /?page=0 returns first page", async () => {
    const res = await anonFetch("/?page=0");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Page 1");
  });

  test("GET / with search and sort combined", async () => {
    const res = await anonFetch("/?q=test&sort=newest&page=0");
    expect(res.status).toBe(200);
  });
});
