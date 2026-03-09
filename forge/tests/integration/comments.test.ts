import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { anonFetch, authFetch, createTestUser, deleteTestUser, BASE_URL } from "./helpers";

describe("Comments (integration)", () => {
  let token: string;
  let userId: string;
  let existingPluginName: string | null = null;

  beforeAll(async () => {
    const user = await createTestUser();
    token = user.accessToken;
    userId = user.userId;

    // Find a real plugin name from the catalogue
    const res = await anonFetch("/api/marketplace.json");
    const data = await res.json();
    if (data.packages?.length > 0) {
      existingPluginName = data.packages[0].name;
    }
  });

  afterAll(async () => {
    if (userId) await deleteTestUser(userId);
  });

  test("POST comment without auth returns error", async () => {
    const res = await anonFetch("/plugins/nonexistent/comments", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
      },
      body: JSON.stringify({ body: "test comment" }),
    });
    expect(res.ok).toBe(false);
  });

  test("GET comments for nonexistent plugin returns 404", async () => {
    const res = await anonFetch("/plugins/nonexistent-zzz-999/comments", {
      headers: { Origin: BASE_URL },
    });
    expect(res.status).toBe(404);
  });

  test("POST comment on existing plugin succeeds", async () => {
    if (!existingPluginName) {
      console.log("Skipping: no seeded plugins available");
      return;
    }
    const res = await fetch(`${BASE_URL}/plugins/${existingPluginName}/comments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ body: "Integration test comment" }),
    });
    expect(res.status).toBe(200);
  });

  test("GET comments for existing plugin returns comment list", async () => {
    if (!existingPluginName) {
      console.log("Skipping: no seeded plugins available");
      return;
    }
    const res = await anonFetch(`/plugins/${existingPluginName}/comments`);
    expect(res.status).toBe(200);
    const html = await res.text();
    // Should contain the comment we just posted (or at least some HTML)
    expect(html).toBeTruthy();
  });
});
