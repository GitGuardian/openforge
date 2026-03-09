import { describe, expect, test, mock, beforeEach, spyOn } from "bun:test";

// ---------------------------------------------------------------------------
// Mock state
// ---------------------------------------------------------------------------

let selectResults: unknown[][] = [];

function nextSelect(): unknown[] {
  return selectResults.shift() ?? [];
}

// ---------------------------------------------------------------------------
// Mock db module
// ---------------------------------------------------------------------------

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => {
        const rows = nextSelect();
        const result = Promise.resolve(rows);
        (result as any).where = () => {
          const whereResult = Promise.resolve(rows);
          (whereResult as any).limit = () => Promise.resolve(rows);
          return whereResult;
        };
        return result;
      },
    }),
  },
}));

// Import AFTER mocking
const { notifySubmissionReviewed } = await import("../../src/lib/notifications");

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("notifySubmissionReviewed", () => {
  beforeEach(() => {
    selectResults = [];
  });

  test("sends approval email to submitter", async () => {
    // First select: submission lookup
    selectResults.push([
      { id: "sub-001", userId: "user-001", gitUrl: "https://github.com/owner/repo", status: "approved" },
    ]);
    // Second select: user lookup
    selectResults.push([
      { id: "user-001", email: "submitter@example.com" },
    ]);

    const consoleSpy = spyOn(console, "log").mockImplementation(() => {});
    await notifySubmissionReviewed("sub-001", "approved");
    expect(consoleSpy).toHaveBeenCalled();
    const logArgs = consoleSpy.mock.calls.flat().join(" ");
    expect(logArgs).toContain("submitter@example.com");
    expect(logArgs).toContain("approved");
    consoleSpy.mockRestore();
  });

  test("sends rejection email with review note", async () => {
    selectResults.push([
      { id: "sub-002", userId: "user-001", gitUrl: "https://github.com/owner/repo", status: "rejected", reviewNote: "Missing README" },
    ]);
    selectResults.push([
      { id: "user-001", email: "submitter@example.com" },
    ]);

    const consoleSpy = spyOn(console, "log").mockImplementation(() => {});
    await notifySubmissionReviewed("sub-002", "rejected", "Missing README");
    expect(consoleSpy).toHaveBeenCalled();
    const logArgs = consoleSpy.mock.calls.flat().join(" ");
    expect(logArgs).toContain("submitter@example.com");
    expect(logArgs).toContain("rejected");
    expect(logArgs).toContain("Missing README");
    consoleSpy.mockRestore();
  });

  test("does not throw if submission not found", async () => {
    selectResults.push([]); // no submission
    await expect(notifySubmissionReviewed("nonexistent", "approved")).resolves.toBeUndefined();
  });

  test("does not throw if user not found", async () => {
    selectResults.push([
      { id: "sub-001", userId: "user-001", gitUrl: "https://github.com/owner/repo", status: "approved" },
    ]);
    selectResults.push([]); // no user
    await expect(notifySubmissionReviewed("sub-001", "approved")).resolves.toBeUndefined();
  });
});
