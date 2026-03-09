import { Hono } from "hono";
import { eq, and, inArray } from "drizzle-orm";
import { db } from "../db";
import { submissions, plugins } from "../db/schema";
import { indexSubmission } from "../lib/indexer";
import { notifySubmissionReviewed } from "../lib/notifications";
import type { AppEnv } from "../types";

export const submissionRoutes = new Hono<AppEnv>();

const GIT_URL_PATTERN =
  /^https:\/\/(github\.com|gitlab\.com)\/[\w.-]+\/[\w.-]+(\.git)?$/;

// ---------------------------------------------------------------------------
// POST /api/submissions — create a submission
// ---------------------------------------------------------------------------

submissionRoutes.post("/api/submissions", async (c) => {
  const user = c.get("user");
  if (!user) return c.json({ error: "Unauthorized" }, 401);

  // Parse body — support both JSON (CLI) and form data (HTMX)
  let gitUrl: string | undefined;
  let description: string | null = null;

  const contentType = c.req.header("Content-Type") || "";
  if (contentType.includes("application/json")) {
    const body = await c.req.json().catch(() => null);
    gitUrl = body?.gitUrl;
    description = typeof body?.description === "string" ? body.description : null;
  } else {
    const formData = await c.req.parseBody();
    gitUrl = typeof formData.gitUrl === "string" ? formData.gitUrl : undefined;
    description = typeof formData.description === "string" ? formData.description : null;
  }

  if (!gitUrl || !gitUrl.trim()) {
    return c.json({ error: "gitUrl is required" }, 400);
  }

  gitUrl = gitUrl.trim();
  if (!GIT_URL_PATTERN.test(gitUrl)) {
    return c.json(
      { error: "Invalid git URL. Must be a GitHub or GitLab repository URL." },
      400,
    );
  }

  // Check for duplicate pending submission with the same gitUrl
  const [existing] = await db
    .select()
    .from(submissions)
    .where(
      and(eq(submissions.gitUrl, gitUrl), eq(submissions.status, "pending")),
    )
    .limit(1);
  if (existing) {
    return c.json(
      { error: "A submission for this URL is already pending review." },
      409,
    );
  }

  const [submission] = await db
    .insert(submissions)
    .values({
      userId: user.id,
      gitUrl,
      description,
      status: "pending",
    })
    .returning();

  // Trigger background indexing — don't block the response
  indexSubmission(submission.id).catch((err) => {
    console.error(`Background indexing failed for submission ${submission.id}:`, err);
  });

  // Return HTML partial for HTMX requests (submit form)
  if (c.req.header("HX-Request")) {
    const { submitSuccess } = await import("../views/submit");
    return c.html(submitSuccess(submission.id));
  }

  return c.json(
    { id: submission.id, status: submission.status, gitUrl: submission.gitUrl },
    201,
  );
});

// ---------------------------------------------------------------------------
// GET /api/submissions — list submissions
// ---------------------------------------------------------------------------

submissionRoutes.get("/api/submissions", async (c) => {
  const user = c.get("user");
  if (!user) return c.json({ error: "Unauthorized" }, 401);

  const isCuratorOrAdmin = user.role === "curator" || user.role === "admin";

  const results = isCuratorOrAdmin
    ? await db.select().from(submissions)
    : await db
        .select()
        .from(submissions)
        .where(eq(submissions.userId, user.id));

  return c.json(results);
});

// ---------------------------------------------------------------------------
// POST /api/submissions/:id/review — curator approves or rejects
// ---------------------------------------------------------------------------

submissionRoutes.post("/api/submissions/:id/review", async (c) => {
  const user = c.get("user");
  if (!user) return c.json({ error: "Unauthorized" }, 401);
  if (user.role !== "curator" && user.role !== "admin") {
    return c.json({ error: "Forbidden" }, 403);
  }

  const body = await c.req.json().catch(() => null);
  if (!body || !["approve", "reject"].includes(body.action)) {
    return c.json({ error: "action must be 'approve' or 'reject'" }, 400);
  }

  const submissionId = c.req.param("id");
  const [submission] = await db
    .select()
    .from(submissions)
    .where(eq(submissions.id, submissionId));

  if (!submission) return c.json({ error: "Submission not found" }, 404);
  if (submission.status !== "pending") {
    return c.json({ error: "Submission already reviewed" }, 409);
  }

  const newStatus = body.action === "approve" ? "approved" : "rejected";

  const [updated] = await db
    .update(submissions)
    .set({
      status: newStatus,
      reviewerId: user.id,
      reviewNote: typeof body.note === "string" ? body.note : null,
      reviewedAt: new Date(),
    })
    .where(eq(submissions.id, submissionId))
    .returning();

  // Update linked plugin status if one exists
  if (submission.pluginId) {
    await db
      .update(plugins)
      .set({ status: newStatus })
      .where(eq(plugins.id, submission.pluginId));
  }

  // Notify submitter — fire-and-forget
  notifySubmissionReviewed(submissionId, newStatus, updated.reviewNote).catch((err) => {
    console.error(`Notification failed for submission ${submissionId}:`, err);
  });

  // Return HTML partial for HTMX requests
  if (c.req.header("HX-Request")) {
    const message =
      newStatus === "approved"
        ? `<div class="text-green-700 font-medium">Plugin approved and now visible in catalogue.</div>`
        : `<div class="text-red-700 font-medium">Plugin rejected.</div>`;
    return c.html(message);
  }

  return c.json({ id: updated.id, status: updated.status });
});
