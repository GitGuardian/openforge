import { Hono } from "hono";
import { serveStatic } from "hono/bun";
import { csrf } from "hono/csrf";
import { logger } from "hono/logger";
import { authMiddleware } from "./middleware/auth";
import { healthRoutes } from "./routes/health";
import { pageRoutes } from "./routes/pages";
import { apiRoutes } from "./routes/api";
import { authRoutes } from "./routes/auth";
import { voteRoutes } from "./routes/votes";
import { commentRoutes } from "./routes/comments";
import { webhookRoutes } from "./routes/webhooks";
import { submissionRoutes } from "./routes/submissions";
import type { AppEnv } from "./types";

const app = new Hono<AppEnv>();

// Middleware
app.use("*", logger());

// Webhook route registered before CSRF — GitHub POSTs don't carry CSRF tokens.
// HMAC signature verification provides equivalent protection.
app.route("/", webhookRoutes);

// Submissions API registered before CSRF — CLI clients use Bearer token auth,
// not browser cookies, so CSRF protection is not needed (or possible).
// Auth middleware is applied inline so user context is available.
app.use("/api/submissions/*", authMiddleware);
app.use("/api/submissions", authMiddleware);
app.route("/", submissionRoutes);

app.use("*", csrf());
app.use("*", authMiddleware);

// Static files
app.use("/public/*", serveStatic({ root: "./" }));

// Routes — more specific routes first
app.route("/", healthRoutes);
app.route("/", authRoutes);
app.route("/", voteRoutes);
app.route("/", commentRoutes);
app.route("/", apiRoutes);
app.route("/", pageRoutes);

// Global error handler
app.onError((err, c) => {
  console.error("Unhandled error:", err);
  if (err instanceof Error && err.message.includes("LOGIN_REQUIRED")) {
    return c.redirect("/auth/login");
  }
  return c.text("Internal Server Error", 500);
});

const port = parseInt(process.env.PORT || "3000");
console.log(`OpenForge running on http://localhost:${port}`);

export default {
  port,
  fetch: app.fetch,
};
