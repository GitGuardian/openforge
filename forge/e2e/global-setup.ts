import { request } from "@playwright/test";
import { ensureTestPlugin } from "./helpers";

export default async function globalSetup() {
  const ctx = await request.newContext({
    baseURL: process.env.FORGE_URL || "http://localhost:3000",
  });
  await ensureTestPlugin(ctx);
  await ctx.dispose();
}
