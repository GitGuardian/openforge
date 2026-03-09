import { eq } from "drizzle-orm";
import { db } from "../db";
import { submissions, users } from "../db/schema";

/**
 * Notify the submitter about a review decision.
 * Fire-and-forget — logs instead of sending real email for now.
 * Replace console.log with actual email transport (SMTP / Supabase Edge Function) in production.
 */
export async function notifySubmissionReviewed(
  submissionId: string,
  status: "approved" | "rejected",
  reviewNote?: string | null,
): Promise<void> {
  const [submission] = await db
    .select()
    .from(submissions)
    .where(eq(submissions.id, submissionId))
    .limit(1);

  if (!submission) return;

  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.id, submission.userId))
    .limit(1);

  if (!user) return;

  const subject =
    status === "approved"
      ? `Your plugin submission has been approved`
      : `Your plugin submission has been rejected`;

  const body =
    status === "approved"
      ? `Your submission for ${submission.gitUrl} has been approved and is now visible in the catalogue.`
      : `Your submission for ${submission.gitUrl} has been rejected.${reviewNote ? ` Reason: ${reviewNote}` : ""}`;

  // TODO: Replace with real email transport
  console.log(
    `[notification] To: ${user.email} | Status: ${status} | Subject: ${subject} | Body: ${body}`,
  );
}
