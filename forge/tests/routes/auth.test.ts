import { describe, expect, test, mock, beforeEach, afterEach } from "bun:test";
import { Hono } from "hono";
import type { AppEnv } from "../../src/types";

// ---------------------------------------------------------------------------
// Configurable mock state
// ---------------------------------------------------------------------------

let mockSignInResult: { data: { session: unknown }; error: unknown } = {
  data: { session: null },
  error: null,
};
let mockSignUpResult: { data: { session: unknown }; error: unknown } = {
  data: { session: null },
  error: null,
};
let mockOtpResult: { error: unknown } = { error: null };
let mockVerifyResult: { data: { session: unknown }; error: unknown } = {
  data: { session: null },
  error: null,
};
let mockAllowedDomains: Array<{ domain: string }> = [];

// ---------------------------------------------------------------------------
// Mock modules
// ---------------------------------------------------------------------------

mock.module("../../src/lib/supabase", () => ({
  supabase: {
    auth: {
      signInWithPassword: async () => mockSignInResult,
      signUp: async () => mockSignUpResult,
      signInWithOtp: async () => mockOtpResult,
      verifyOtp: async () => mockVerifyResult,
      getUser: async () => ({ data: { user: null }, error: null }),
    },
  },
  supabaseAdmin: null,
}));

mock.module("../../src/db", () => ({
  db: {
    select: () => ({
      from: () => ({
        where: () => Promise.resolve(mockAllowedDomains),
      }),
    }),
  },
}));

const { authRoutes } = await import("../../src/routes/auth");

// ---------------------------------------------------------------------------
// App factory
// ---------------------------------------------------------------------------

function createAuthApp(): Hono<AppEnv> {
  const app = new Hono<AppEnv>();
  app.use("*", async (c, next) => {
    c.set("user", null);
    await next();
  });
  app.route("/", authRoutes);
  return app;
}

// ---------------------------------------------------------------------------
// Tests: GET form rendering
// ---------------------------------------------------------------------------

describe("GET /auth/login", () => {
  test("returns 200 with login form", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/login");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Sign in to OpenForge");
    expect(html).toContain('action="/auth/login"');
    expect(html).toContain('type="email"');
    expect(html).toContain('type="password"');
  });

  test("displays error message from query param", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/login?error=Invalid+credentials");
    const html = await res.text();
    expect(html).toContain("Invalid credentials");
    expect(html).toContain("bg-red-50");
  });

  test("shows magic link and signup links", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/login");
    const html = await res.text();
    expect(html).toContain("/auth/magic-link");
    expect(html).toContain("/auth/signup");
  });
});

describe("GET /auth/signup", () => {
  test("returns 200 with signup form", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/signup");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Create your account");
    expect(html).toContain('action="/auth/signup"');
    expect(html).toContain("confirm_password");
  });

  test("shows link back to login", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/signup");
    const html = await res.text();
    expect(html).toContain("/auth/login");
    expect(html).toContain("Already have an account");
  });
});

describe("GET /auth/magic-link", () => {
  test("returns 200 with magic link form", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/magic-link");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Sign in with magic link");
    expect(html).toContain('action="/auth/magic-link"');
  });

  test("shows success banner when success=1", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/magic-link?success=1");
    const html = await res.text();
    expect(html).toContain("Check your email");
    expect(html).toContain("bg-green-50");
  });
});

// ---------------------------------------------------------------------------
// Tests: POST /auth/login
// ---------------------------------------------------------------------------

describe("POST /auth/login", () => {
  beforeEach(() => {
    mockSignInResult = { data: { session: null }, error: null };
  });

  test("redirects to error on missing email/password", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=&password=",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("/auth/login?error=");
  });

  test("redirects to error on Supabase auth failure", async () => {
    mockSignInResult = {
      data: { session: null },
      error: { message: "Invalid credentials" },
    };
    const app = createAuthApp();
    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com&password=wrong",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("error=Invalid");
  });

  test("sets auth cookies and redirects to / on success", async () => {
    mockSignInResult = {
      data: {
        session: {
          access_token: "test-access",
          refresh_token: "test-refresh",
        },
      },
      error: null,
    };
    const app = createAuthApp();
    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com&password=correct",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/");
    const cookies = res.headers.getAll("Set-Cookie");
    expect(cookies.some((c: string) => c.includes("sb-access-token"))).toBe(true);
    expect(cookies.some((c: string) => c.includes("sb-refresh-token"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Tests: POST /auth/signup
// ---------------------------------------------------------------------------

describe("POST /auth/signup", () => {
  const originalMode = process.env.OPENFORGE_MODE;

  beforeEach(() => {
    mockSignUpResult = { data: { session: null }, error: null };
    mockAllowedDomains = [];
    delete process.env.OPENFORGE_MODE;
  });

  afterEach(() => {
    if (originalMode !== undefined) {
      process.env.OPENFORGE_MODE = originalMode;
    } else {
      delete process.env.OPENFORGE_MODE;
    }
  });

  test("redirects to error on missing fields", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=&password=&confirm_password=",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("error=");
  });

  test("rejects mismatched passwords", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com&password=password1&confirm_password=password2",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("Passwords+do+not+match");
  });

  test("rejects short passwords", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com&password=short&confirm_password=short",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("8+characters");
  });

  test("rejects disallowed domain in private mode", async () => {
    process.env.OPENFORGE_MODE = "private";
    mockAllowedDomains = []; // no domains allowed
    const app = createAuthApp();
    const res = await app.request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@blocked.com&password=longenough&confirm_password=longenough",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("domain+is+not+allowed");
  });

  test("allows domain in private mode when listed", async () => {
    process.env.OPENFORGE_MODE = "private";
    mockAllowedDomains = [{ domain: "allowed.com" }];
    mockSignUpResult = { data: { session: null }, error: null };
    const app = createAuthApp();
    const res = await app.request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@allowed.com&password=longenough&confirm_password=longenough",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    // Should redirect to login with confirmation message (no session returned)
    expect(res.headers.get("Location")).toContain("/auth/login");
  });

  test("sets cookies on immediate session (no email confirmation)", async () => {
    mockSignUpResult = {
      data: {
        session: {
          access_token: "new-access",
          refresh_token: "new-refresh",
        },
      },
      error: null,
    };
    const app = createAuthApp();
    const res = await app.request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com&password=longenough&confirm_password=longenough",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/");
  });

  test("redirects to error on Supabase signup failure", async () => {
    mockSignUpResult = {
      data: { session: null },
      error: { message: "User already exists" },
    };
    const app = createAuthApp();
    const res = await app.request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com&password=longenough&confirm_password=longenough",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("User%20already%20exists");
  });
});

// ---------------------------------------------------------------------------
// Tests: POST /auth/magic-link
// ---------------------------------------------------------------------------

describe("POST /auth/magic-link", () => {
  const originalMode = process.env.OPENFORGE_MODE;

  beforeEach(() => {
    mockOtpResult = { error: null };
    mockAllowedDomains = [];
    delete process.env.OPENFORGE_MODE;
  });

  afterEach(() => {
    if (originalMode !== undefined) {
      process.env.OPENFORGE_MODE = originalMode;
    } else {
      delete process.env.OPENFORGE_MODE;
    }
  });

  test("redirects to error on empty email", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/magic-link", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("error=Email");
  });

  test("redirects to success on valid email", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/magic-link", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("success=1");
  });

  test("rejects disallowed domain in private mode", async () => {
    process.env.OPENFORGE_MODE = "private";
    mockAllowedDomains = [];
    const app = createAuthApp();
    const res = await app.request("/auth/magic-link", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@blocked.com",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("domain+is+not+allowed");
  });

  test("redirects to error on OTP failure", async () => {
    mockOtpResult = { error: { message: "Rate limited" } };
    const app = createAuthApp();
    const res = await app.request("/auth/magic-link", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=test@example.com",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("Rate%20limited");
  });
});

// ---------------------------------------------------------------------------
// Tests: GET /auth/callback
// ---------------------------------------------------------------------------

describe("GET /auth/callback", () => {
  beforeEach(() => {
    mockVerifyResult = { data: { session: null }, error: null };
  });

  test("redirects to error on missing params", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/callback", { redirect: "manual" });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("Invalid+callback");
  });

  test("redirects to error on verify failure", async () => {
    mockVerifyResult = {
      data: { session: null },
      error: { message: "Expired link" },
    };
    const app = createAuthApp();
    const res = await app.request(
      "/auth/callback?token_hash=abc&type=magiclink",
      { redirect: "manual" },
    );
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toContain("Expired%20link");
  });

  test("sets cookies and redirects on success", async () => {
    mockVerifyResult = {
      data: {
        session: {
          access_token: "callback-access",
          refresh_token: "callback-refresh",
        },
      },
      error: null,
    };
    const app = createAuthApp();
    const res = await app.request(
      "/auth/callback?token_hash=abc&type=magiclink",
      { redirect: "manual" },
    );
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/");
    const cookies = res.headers.getAll("Set-Cookie");
    expect(cookies.some((c: string) => c.includes("sb-access-token"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Tests: POST /auth/logout
// ---------------------------------------------------------------------------

describe("POST /auth/logout", () => {
  test("clears cookies and redirects to login", async () => {
    const app = createAuthApp();
    const res = await app.request("/auth/logout", {
      method: "POST",
      redirect: "manual",
    });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe("/auth/login");
    const cookies = res.headers.getAll("Set-Cookie");
    const accessClear = cookies.some(
      (c: string) => c.includes("sb-access-token") && c.includes("Max-Age=0"),
    );
    expect(accessClear).toBe(true);
  });
});
