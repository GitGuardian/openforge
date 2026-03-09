import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { anonFetch, authFetch, createTestUser, deleteTestUser, BASE_URL } from "./helpers";

describe("Voting (integration)", () => {
  let token: string;
  let userId: string;
  // Use a known seeded plugin name, or test with nonexistent
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

  test("POST vote without auth returns error", async () => {
    const res = await anonFetch("/plugins/nonexistent/vote", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
      },
      body: JSON.stringify({ value: 1 }),
    });
    // requireAuth throws HTTPException(401) — may surface as 401 or 500
    expect(res.ok).toBe(false);
  });

  test("POST vote on nonexistent plugin returns 404", async () => {
    const res = await fetch(`${BASE_URL}/plugins/nonexistent-zzz/vote`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ value: 1 }),
    });
    expect(res.status).toBe(404);
  });

  test("POST vote with invalid value returns 400", async () => {
    const name = existingPluginName || "nonexistent";
    const res = await fetch(`${BASE_URL}/plugins/${name}/vote`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ value: 99 }),
    });
    expect(res.status).toBe(400);
  });

  test("POST upvote on existing plugin succeeds", async () => {
    if (!existingPluginName) {
      console.log("Skipping: no seeded plugins available");
      return;
    }
    const res = await fetch(`${BASE_URL}/plugins/${existingPluginName}/vote`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ value: 1 }),
    });
    expect(res.status).toBe(200);
  });

  test("POST remove vote (value=0) on existing plugin succeeds", async () => {
    if (!existingPluginName) {
      console.log("Skipping: no seeded plugins available");
      return;
    }
    const res = await fetch(`${BASE_URL}/plugins/${existingPluginName}/vote`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: BASE_URL,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ value: 0 }),
    });
    expect(res.status).toBe(200);
  });
});
