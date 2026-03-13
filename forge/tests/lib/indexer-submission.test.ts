import { describe, expect, test, mock, beforeEach, spyOn } from "bun:test";

// ---------------------------------------------------------------------------
// Mock state
// ---------------------------------------------------------------------------

let lastRejectSetValues: Record<string, unknown> | null = null;
let mockSubmission: Record<string, unknown> | null = null;

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => {
        // First call: look up submission; second call: look up registries
        const result = Promise.resolve(mockSubmission ? [mockSubmission] : []);
        (result as any).where = () => {
          const wr = Promise.resolve(mockSubmission ? [mockSubmission] : []);
          (wr as any).limit = () => Promise.resolve(mockSubmission ? [mockSubmission] : []);
          return wr;
        };
        return result;
      },
    }),
    update: () => ({
      set: (values: Record<string, unknown>) => {
        lastRejectSetValues = values;
        return {
          where: () => Promise.resolve(),
        };
      },
    }),
    insert: () => ({
      values: () => ({
        returning: () =>
          Promise.resolve([{ id: "reg-new", name: "test", gitUrl: "https://github.com/owner/repo" }]),
      }),
    }),
  },
}));

mock.module("../../src/lib/markdown", () => ({
  renderMarkdown: (s: string) => `<p>${s}</p>`,
}));

const { indexSubmission } = await import("../../src/lib/indexer");

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("indexSubmission — reviewNote sanitization", () => {
  beforeEach(() => {
    lastRejectSetValues = null;
    mockSubmission = {
      id: "sub-001",
      gitUrl: "https://github.com/owner/nonexistent-repo",
      status: "pending",
    };
  });

  test("stores generic message in reviewNote when clone fails, not raw error", async () => {
    const errorSpy = spyOn(console, "error").mockImplementation(() => {});
    const logSpy = spyOn(console, "log").mockImplementation(() => {});

    await indexSubmission("sub-001");

    // The reviewNote should NOT contain raw git/filesystem error details
    expect(lastRejectSetValues).not.toBeNull();
    const reviewNote = lastRejectSetValues!.reviewNote as string;
    expect(reviewNote).not.toContain("exit code");
    expect(reviewNote).not.toContain("git clone");
    expect(reviewNote).toContain("please verify");

    errorSpy.mockRestore();
    logSpy.mockRestore();
  });

  test("logs detailed error to console when clone fails", async () => {
    const errorSpy = spyOn(console, "error").mockImplementation(() => {});
    const logSpy = spyOn(console, "log").mockImplementation(() => {});

    await indexSubmission("sub-001");

    // Detailed error should be logged server-side
    const errorCalls = errorSpy.mock.calls.flat().map(String).join(" ");
    expect(errorCalls).toContain("sub-001");

    errorSpy.mockRestore();
    logSpy.mockRestore();
  });
});
