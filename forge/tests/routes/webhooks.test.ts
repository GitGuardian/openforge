import { describe, expect, test, mock, beforeEach } from "bun:test";
import { Hono } from "hono";
import type { AppEnv } from "../../src/types";

// ---------------------------------------------------------------------------
// HMAC helper — compute a valid signature for testing
// ---------------------------------------------------------------------------

function signPayload(secret: string, body: string): string {
  const hmac = new Bun.CryptoHasher("sha256", secret);
  hmac.update(body);
  return `sha256=${hmac.digest("hex")}`;
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const TEST_SECRET = "test-webhook-secret-123";

function makeRegistry(overrides: Record<string, unknown> = {}) {
  return {
    id: "reg-00000000-0000-0000-0000-000000000001",
    name: "test-registry",
    gitUrl: "https://github.com/test-org/test-repo",
    registryType: "github",
    webhookSecret: TEST_SECRET,
    indexedAt: null,
    createdAt: new Date(),
    ...overrides,
  };
}

function makePushPayload(overrides: Record<string, unknown> = {}) {
  return {
    ref: "refs/heads/main",
    repository: {
      clone_url: "https://github.com/test-org/test-repo.git",
      html_url: "https://github.com/test-org/test-repo",
    },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockRegistries: ReturnType<typeof makeRegistry>[] = [];
let mockUpdateCalls: unknown[] = [];
let mockIndexCalls: string[] = [];

// Mock the db module
mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => Promise.resolve(mockRegistries),
    }),
    update: () => ({
      set: (values: unknown) => ({
        where: (condition: unknown) => {
          mockUpdateCalls.push({ values, condition });
          return Promise.resolve();
        },
      }),
    }),
  },
}));

// Mock the indexer module
mock.module("../../src/lib/indexer", () => ({
  indexRegistry: (id: string) => {
    mockIndexCalls.push(id);
    return Promise.resolve({
      pluginsFound: 1,
      skillsFound: 2,
      pluginsRemoved: 0,
      skillsRemoved: 0,
      errors: [],
    });
  },
  indexSubmission: () => Promise.resolve(),
}));

// Import AFTER mocking
const { webhookRoutes } = await import("../../src/routes/webhooks");

// ---------------------------------------------------------------------------
// Helper to send a webhook request
// ---------------------------------------------------------------------------

async function webhookRequest(
  body: string,
  headers: Record<string, string> = {},
): Promise<Response> {
  return await webhookRoutes.request("/api/webhooks/github", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("POST /api/webhooks/github", () => {
  beforeEach(() => {
    mockRegistries = [makeRegistry()];
    mockUpdateCalls = [];
    mockIndexCalls = [];
  });

  // --- Event filtering ---

  test("ignores non-push events", async () => {
    const res = await webhookRequest("{}", {
      "X-GitHub-Event": "ping",
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("ignored event");
  });

  test("ignores requests with no event header", async () => {
    const res = await webhookRequest("{}");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("ignored event");
  });

  // --- Signature validation ---

  test("rejects push without signature header", async () => {
    const res = await webhookRequest("{}", {
      "X-GitHub-Event": "push",
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBe("missing signature");
  });

  test("rejects invalid JSON body", async () => {
    const rawBody = "not json";
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("invalid JSON");
  });

  // --- Ref filtering ---

  test("ignores tag pushes", async () => {
    const payload = makePushPayload({ ref: "refs/tags/v1.0.0" });
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("ignored non-branch ref");
  });

  test("ignores payloads with no ref", async () => {
    const payload = makePushPayload({ ref: undefined });
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("ignored non-branch ref");
  });

  // --- Repository URL handling ---

  test("rejects payloads with no repository URL", async () => {
    const payload = { ref: "refs/heads/main", repository: {} };
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("no repository URL in payload");
  });

  test("returns 401 when no matching registry (HMAC fails)", async () => {
    mockRegistries = []; // no registries — HMAC can't match any
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBe("invalid signature");
  });

  // --- URL normalization ---

  test("matches registry URL with .git suffix", async () => {
    // Registry has URL without .git, payload has .git
    mockRegistries = [makeRegistry({ gitUrl: "https://github.com/test-org/test-repo" })];
    const payload = makePushPayload({
      repository: {
        clone_url: "https://github.com/test-org/test-repo.git",
      },
    });
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("indexing started");
  });

  test("matches registry URL with trailing slash", async () => {
    mockRegistries = [makeRegistry({ gitUrl: "https://github.com/test-org/test-repo/" })];
    const payload = makePushPayload({
      repository: {
        clone_url: "https://github.com/test-org/test-repo",
      },
    });
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("indexing started");
  });

  // --- HMAC verification ---

  test("rejects invalid HMAC regardless of payload URL", async () => {
    // Even with a matching repo URL, invalid signature should be 401
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
    });
    expect(res.status).toBe(401);
  });

  test("matches registry by HMAC, not by URL", async () => {
    // Two registries with different URLs, only one secret matches
    const secret2 = "other-secret";
    mockRegistries = [
      makeRegistry({ id: "reg-1", gitUrl: "https://github.com/org/repo-a", webhookSecret: "wrong-secret" }),
      makeRegistry({ id: "reg-2", gitUrl: "https://github.com/org/repo-b", webhookSecret: secret2 }),
    ];
    // Payload URL doesn't match either registry — but HMAC matches reg-2
    const payload = makePushPayload({
      repository: { clone_url: "https://github.com/org/repo-b.git" },
    });
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(secret2, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("indexing started");
    expect(mockIndexCalls).toContain("reg-2");
  });

  test("rejects webhook when registry has no secret configured", async () => {
    mockRegistries = [makeRegistry({ webhookSecret: null })];
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    // No secret to verify against → HMAC match fails
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBe("invalid signature");
  });

  test("rejects webhook with wrong signature", async () => {
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload("wrong-secret", rawBody),
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBe("invalid signature");
  });

  test("rejects webhook with malformed signature", async () => {
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": "not-a-valid-signature",
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBe("invalid signature");
  });

  // --- Concurrency guard ---

  test("skips indexing if indexed less than 60s ago", async () => {
    mockRegistries = [makeRegistry({ indexedAt: new Date() })]; // just now
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("indexing already in progress");
    expect(mockIndexCalls).toHaveLength(0);
  });

  test("allows indexing if indexed more than 60s ago", async () => {
    const oldDate = new Date(Date.now() - 120_000); // 2 minutes ago
    mockRegistries = [makeRegistry({ indexedAt: oldDate })];
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("indexing started");
  });

  // --- Happy path ---

  test("valid webhook triggers indexing", async () => {
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("indexing started");
    expect(mockIndexCalls).toContain("reg-00000000-0000-0000-0000-000000000001");
  });

  test("updates indexedAt before starting indexing", async () => {
    const payload = makePushPayload();
    const rawBody = JSON.stringify(payload);
    await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(mockUpdateCalls).toHaveLength(1);
  });

  test("uses html_url when clone_url is missing", async () => {
    const payload = makePushPayload({
      repository: {
        html_url: "https://github.com/test-org/test-repo",
      },
    });
    const rawBody = JSON.stringify(payload);
    const res = await webhookRequest(rawBody, {
      "X-GitHub-Event": "push",
      "X-Hub-Signature-256": signPayload(TEST_SECRET, rawBody),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("indexing started");
  });
});
