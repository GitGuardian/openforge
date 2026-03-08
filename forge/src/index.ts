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
import type { AppEnv } from "./types";

const app = new Hono<AppEnv>();

// Middleware
app.use("*", logger());
app.use("*", csrf());
app.use("*", authMiddleware);

// Static files
app.use("/public/*", serveStatic({ root: "./" }));

// Routes — more specific routes first
app.route("/", healthRoutes);
app.route("/", authRoutes);
app.route("/", voteRoutes);
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
