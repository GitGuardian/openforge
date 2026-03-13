import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { serveStatic } from "hono/bun";
import { csrf } from "hono/csrf";
import { secureHeaders } from "hono/secure-headers";
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
app.use("*", secureHeaders());

// Webhook route registered before CSRF — GitHub POSTs don't carry CSRF tokens.
// HMAC signature verification provides equivalent protection.
app.route("/", webhookRoutes);

// Test-only endpoint: reset rate limits between E2E test runs (before CSRF)
if (process.env.NODE_ENV === "test") {
  const { resetRateLimits } = await import("./lib/rate-limit");
  app.post("/_test/reset-rate-limits", (c) => {
    resetRateLimits();
    return c.json({ reset: true });
  });
}

app.use("*", csrf());
app.use("*", authMiddleware);

// Submissions routes are after CSRF so cookie-auth requests are protected.
// CLI clients using Bearer tokens are not affected — Hono's csrf() checks
// Origin header which is only sent by browsers.
app.route("/", submissionRoutes);

// Static files
app.use("/public/*", serveStatic({ root: "./" }));

// Routes — more specific routes first
app.route("/", healthRoutes);
app.route("/", authRoutes);
app.route("/", voteRoutes);
app.route("/", commentRoutes);
app.route("/", apiRoutes);
app.route("/", pageRoutes);

// (test endpoint registered before CSRF above)

// Global error handler
app.onError((err, c) => {
  if (err instanceof HTTPException) {
    return err.getResponse();
  }
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
