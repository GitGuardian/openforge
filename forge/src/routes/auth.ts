import { Hono } from "hono";
import { html } from "hono/html";
import { setCookie, deleteCookie } from "hono/cookie";
import { eq } from "drizzle-orm";
import { db } from "../db";
import { allowedDomains } from "../db/schema";
import { supabase } from "../lib/supabase";
import { checkRateLimit } from "../lib/rate-limit";
import type { AppEnv } from "../types";
import type { Context } from "hono";

export const authRoutes = new Hono<AppEnv>();

// ---------------------------------------------------------------------------
// Cookie helpers
// ---------------------------------------------------------------------------

function setAuthCookies(
  c: Context,
  session: { access_token: string; refresh_token: string },
): void {
  const isSecure = c.req.url.startsWith("https");
  setCookie(c, "sb-access-token", session.access_token, {
    httpOnly: true,
    secure: isSecure,
    sameSite: "Lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });
  setCookie(c, "sb-refresh-token", session.refresh_token, {
    httpOnly: true,
    secure: isSecure,
    sameSite: "Lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
}

function clearAuthCookies(c: Context): void {
  deleteCookie(c, "sb-access-token", { path: "/" });
  deleteCookie(c, "sb-refresh-token", { path: "/" });
}

// ---------------------------------------------------------------------------
// Domain allow-list (private mode)
// ---------------------------------------------------------------------------

async function isEmailDomainAllowed(email: string): Promise<boolean> {
  const mode = process.env.OPENFORGE_MODE;
  if (mode !== "private") return true;

  const domain = email.split("@")[1]?.toLowerCase();
  if (!domain) return false;

  const allowed = await db
    .select()
    .from(allowedDomains)
    .where(eq(allowedDomains.domain, domain));
  return allowed.length > 0;
}

// ---------------------------------------------------------------------------
// Shared layout for auth pages
// ---------------------------------------------------------------------------

function authLayout(title: string, content: string) {
  return html`<!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${title} - OpenForge</title>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="bg-gray-50 min-h-screen flex items-center justify-center">
        <div class="w-full max-w-md px-4">${html([content] as unknown as TemplateStringsArray)}</div>
      </body>
    </html>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formCard(title: string, body: string, error?: string) {
  const errorBanner = error
    ? `<div class="mb-4 rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">${escapeHtml(error)}</div>`
    : "";

  return `
    <div class="bg-white shadow-md rounded-lg p-8">
      <h1 class="text-2xl font-bold text-gray-900 text-center mb-6">${title}</h1>
      ${errorBanner}
      ${body}
    </div>
  `;
}

function inputField(name: string, label: string, type: string = "text") {
  return `
    <div class="mb-4">
      <label for="${name}" class="block text-sm font-medium text-gray-700 mb-1">${label}</label>
      <input
        type="${type}"
        id="${name}"
        name="${name}"
        required
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
      />
    </div>
  `;
}

function submitButton(label: string) {
  return `
    <button
      type="submit"
      class="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
    >${label}</button>
  `;
}

// ---------------------------------------------------------------------------
// GET /auth/login
// ---------------------------------------------------------------------------

authRoutes.get("/auth/login", (c) => {
  const error = c.req.query("error");
  return c.html(
    authLayout(
      "Sign In",
      formCard(
        "Sign in to OpenForge",
        `
        <form method="POST" action="/auth/login">
          ${inputField("email", "Email", "email")}
          ${inputField("password", "Password", "password")}
          ${submitButton("Sign In")}
        </form>
        <div class="mt-4 text-center text-sm text-gray-500 space-y-1">
          <p><a href="/auth/magic-link" class="text-indigo-600 hover:text-indigo-500">Sign in with magic link</a></p>
          <p><a href="/auth/signup" class="text-indigo-600 hover:text-indigo-500">Create an account</a></p>
        </div>
        `,
        error ?? undefined,
      ),
    ),
  );
});

// ---------------------------------------------------------------------------
// GET /auth/signup
// ---------------------------------------------------------------------------

authRoutes.get("/auth/signup", (c) => {
  const error = c.req.query("error");
  return c.html(
    authLayout(
      "Sign Up",
      formCard(
        "Create your account",
        `
        <form method="POST" action="/auth/signup">
          ${inputField("email", "Email", "email")}
          ${inputField("password", "Password", "password")}
          ${inputField("confirm_password", "Confirm Password", "password")}
          ${submitButton("Create Account")}
        </form>
        <div class="mt-4 text-center text-sm text-gray-500">
          <p>Already have an account? <a href="/auth/login" class="text-indigo-600 hover:text-indigo-500">Sign in</a></p>
        </div>
        `,
        error ?? undefined,
      ),
    ),
  );
});

// ---------------------------------------------------------------------------
// GET /auth/magic-link
// ---------------------------------------------------------------------------

authRoutes.get("/auth/magic-link", (c) => {
  const error = c.req.query("error");
  const success = c.req.query("success");

  const successBanner = success
    ? `<div class="mb-4 rounded-md bg-green-50 border border-green-200 p-3 text-sm text-green-700">Check your email for the magic link.</div>`
    : "";

  return c.html(
    authLayout(
      "Magic Link",
      formCard(
        "Sign in with magic link",
        `
        ${successBanner}
        <form method="POST" action="/auth/magic-link">
          ${inputField("email", "Email", "email")}
          ${submitButton("Send Magic Link")}
        </form>
        <div class="mt-4 text-center text-sm text-gray-500">
          <p><a href="/auth/login" class="text-indigo-600 hover:text-indigo-500">Back to sign in</a></p>
        </div>
        `,
        error ?? undefined,
      ),
    ),
  );
});

// ---------------------------------------------------------------------------
// POST /auth/login
// ---------------------------------------------------------------------------

authRoutes.post("/auth/login", async (c) => {
  const body = await c.req.parseBody();
  const email = String(body.email ?? "");
  const password = String(body.password ?? "");

  const ip = c.req.header("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  if (!checkRateLimit(`auth:login:${ip}:${email}`, 5, 60_000)) {
    return c.text("Too many requests", 429);
  }

  if (!email || !password) {
    return c.redirect("/auth/login?error=Email+and+password+are+required");
  }

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error || !data.session) {
    if (error) console.error("Auth login error:", error.message);
    return c.redirect(
      `/auth/login?error=${encodeURIComponent("Invalid email or password. Please try again.")}`,
    );
  }

  setAuthCookies(c, data.session);
  return c.redirect("/");
});

// ---------------------------------------------------------------------------
// POST /auth/signup
// ---------------------------------------------------------------------------

authRoutes.post("/auth/signup", async (c) => {
  const body = await c.req.parseBody();
  const email = String(body.email ?? "");
  const password = String(body.password ?? "");
  const confirmPassword = String(body.confirm_password ?? "");

  const ip = c.req.header("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  if (!checkRateLimit(`auth:signup:${ip}:${email}`, 3, 60_000)) {
    return c.text("Too many requests", 429);
  }

  if (!email || !password) {
    return c.redirect("/auth/signup?error=Email+and+password+are+required");
  }

  if (password !== confirmPassword) {
    return c.redirect("/auth/signup?error=Passwords+do+not+match");
  }

  if (password.length < 8) {
    return c.redirect(
      "/auth/signup?error=Password+must+be+at+least+8+characters",
    );
  }

  // In private mode, check domain allow-list
  const domainAllowed = await isEmailDomainAllowed(email);
  if (!domainAllowed) {
    return c.redirect(
      "/auth/signup?error=Email+domain+is+not+allowed+for+this+instance",
    );
  }

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
  });

  if (error) {
    console.error("Auth signup error:", error.message);
    return c.redirect(
      `/auth/signup?error=${encodeURIComponent("Signup failed. Please try again.")}`,
    );
  }

  if (data.session) {
    setAuthCookies(c, data.session);
    return c.redirect("/");
  }

  // If email confirmation is required, Supabase won't return a session
  return c.redirect(
    "/auth/login?error=Check+your+email+to+confirm+your+account",
  );
});

// ---------------------------------------------------------------------------
// POST /auth/magic-link
// ---------------------------------------------------------------------------

authRoutes.post("/auth/magic-link", async (c) => {
  const body = await c.req.parseBody();
  const email = String(body.email ?? "");

  const ip = c.req.header("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  if (!checkRateLimit(`auth:magic:${ip}:${email}`, 3, 60_000)) {
    return c.text("Too many requests", 429);
  }

  if (!email) {
    return c.redirect("/auth/magic-link?error=Email+is+required");
  }

  // In private mode, check domain allow-list
  const domainAllowed = await isEmailDomainAllowed(email);
  if (!domainAllowed) {
    return c.redirect(
      "/auth/magic-link?error=Email+domain+is+not+allowed+for+this+instance",
    );
  }

  // Build the callback URL from the current request origin
  const url = new URL(c.req.url);
  const emailRedirectTo = `${url.origin}/auth/callback`;

  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo },
  });

  if (error) {
    console.error("Auth magic-link error:", error.message);
    return c.redirect(
      `/auth/magic-link?error=${encodeURIComponent("Could not send magic link. Please try again.")}`,
    );
  }

  return c.redirect("/auth/magic-link?success=1");
});

// ---------------------------------------------------------------------------
// GET /auth/callback — handle magic link / OAuth callback
// ---------------------------------------------------------------------------

authRoutes.get("/auth/callback", async (c) => {
  // PKCE flow: Supabase redirects with ?code=... query parameter
  const code = c.req.query("code");
  if (code) {
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);
    if (error || !data.session) {
      if (error) console.error("Auth callback error:", error.message);
      return c.redirect(
        `/auth/login?error=${encodeURIComponent("Authentication failed. Please try again.")}`,
      );
    }
    setAuthCookies(c, data.session);
    return c.redirect("/");
  }

  // Legacy implicit flow: token_hash + type params
  const tokenHash = c.req.query("token_hash");
  const type = c.req.query("type");

  if (!tokenHash || !type) {
    return c.redirect("/auth/login?error=Invalid+callback+parameters");
  }

  if (type !== "magiclink" && type !== "email") {
    return c.redirect("/auth/login?error=Invalid+callback+parameters");
  }

  const { data, error } = await supabase.auth.verifyOtp({
    token_hash: tokenHash,
    type,
  });

  if (error || !data.session) {
    if (error) console.error("Auth verify error:", error.message);
    return c.redirect(
      `/auth/login?error=${encodeURIComponent("Authentication failed. Please try again.")}`,
    );
  }

  setAuthCookies(c, data.session);
  return c.redirect("/");
});

// ---------------------------------------------------------------------------
// POST /auth/logout
// ---------------------------------------------------------------------------

authRoutes.post("/auth/logout", (c) => {
  clearAuthCookies(c);
  return c.redirect("/auth/login");
});
