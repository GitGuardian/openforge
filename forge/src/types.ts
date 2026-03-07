// Shared Hono app types — use these when creating route groups
// so they know about middleware-injected variables.

export type AppUser = {
  id: string;
  email: string;
  displayName: string | null;
  role: "user" | "curator" | "admin";
  authId: string;
};

export type AppEnv = {
  Variables: {
    user: AppUser | null;
  };
};
