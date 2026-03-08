import { Hono } from "hono";
import { eq, and, sql } from "drizzle-orm";
import { db } from "../db";
import { plugins, votes } from "../db/schema";
import { requireAuth } from "../middleware/auth";
import { checkRateLimit } from "../lib/rate-limit";
import type { AppEnv } from "../types";
import { voteWidget } from "../views/components/vote-widget";

export const voteRoutes = new Hono<AppEnv>();

// ---------------------------------------------------------------------------
// Downvote policy
// ---------------------------------------------------------------------------

function getDownvotePolicy(): {
  type: "authenticated" | "karma";
  threshold: number;
} {
  const raw =
    process.env.DOWNVOTE_POLICY ??
    (process.env.OPENFORGE_MODE === "private" ? "authenticated" : "karma:10");

  if (raw === "authenticated") {
    return { type: "authenticated", threshold: 0 };
  }

  const match = raw.match(/^karma:(\d+)$/);
  if (match) {
    return { type: "karma", threshold: parseInt(match[1], 10) };
  }

  return { type: "authenticated", threshold: 0 };
}

async function canDownvote(_userId: string): Promise<boolean> {
  const policy = getDownvotePolicy();
  if (policy.type === "authenticated") return true;

  // Count total upvotes received on user's plugins (karma)
  // For MVP: user needs to have received `threshold` upvotes across all their content
  // Since we don't have plugin_owners yet, we skip karma check and allow all authenticated
  // TODO: implement karma check when plugin_owners table is active
  return true;
}

// ---------------------------------------------------------------------------
// POST /plugins/:name/vote
// ---------------------------------------------------------------------------

voteRoutes.post("/plugins/:name/vote", async (c) => {
  const user = requireAuth(c);
  const pluginName = c.req.param("name");

  // Rate limit: 30 votes per user per minute
  if (!checkRateLimit(`vote:${user.id}`, 30, 60_000)) {
    return c.text("Too many requests", 429);
  }

  // Parse and validate value
  const body = await c.req.json();
  const value = body.value;
  if (value !== -1 && value !== 0 && value !== 1) {
    return c.text("Invalid vote value", 400);
  }

  // Check downvote permission
  if (value === -1) {
    const allowed = await canDownvote(user.id);
    if (!allowed) {
      return c.text("Downvoting not permitted", 403);
    }
  }

  // Find the plugin
  const [plugin] = await db
    .select({ id: plugins.id, voteScore: plugins.voteScore })
    .from(plugins)
    .where(eq(plugins.name, pluginName))
    .limit(1);

  if (!plugin) {
    return c.text("Plugin not found", 404);
  }

  // Get existing vote (if any)
  const [existingVote] = await db
    .select()
    .from(votes)
    .where(and(eq(votes.userId, user.id), eq(votes.pluginId, plugin.id)))
    .limit(1);

  const oldValue = existingVote?.value ?? 0;

  if (value === 0) {
    // Remove vote
    if (existingVote) {
      await db
        .delete(votes)
        .where(and(eq(votes.userId, user.id), eq(votes.pluginId, plugin.id)));
    }
  } else if (existingVote) {
    // Update existing vote
    await db
      .update(votes)
      .set({ value })
      .where(and(eq(votes.userId, user.id), eq(votes.pluginId, plugin.id)));
  } else {
    // Insert new vote
    await db.insert(votes).values({
      userId: user.id,
      pluginId: plugin.id,
      value,
    });
  }

  // Update plugin vote_score atomically
  const delta = value - oldValue;
  if (delta !== 0) {
    await db
      .update(plugins)
      .set({ voteScore: sql`${plugins.voteScore} + ${delta}` })
      .where(eq(plugins.id, plugin.id));
  }

  // Return updated widget
  const newScore = plugin.voteScore + delta;
  const userVote = value;
  const showDownvote = c.req.header("HX-Trigger-Name") === "detail-vote";

  return c.html(voteWidget(pluginName, newScore, userVote, showDownvote));
});
