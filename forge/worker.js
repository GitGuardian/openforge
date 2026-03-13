import { Container, getContainer } from "@cloudflare/containers";

export class OpenForgeContainer extends Container {
  defaultPort = 3000;
  sleepAfter = "5m"; // scale-to-zero after 5 min idle
}

export default {
  async fetch(request, env) {
    const container = getContainer(env.OPENFORGE);

    // Secrets set via `wrangler secret put` live in the Worker's env scope only.
    // They must be explicitly passed to the container on startup.
    await container.start({
      envVars: {
        DATABASE_URL: env.DATABASE_URL,
        SUPABASE_URL: env.SUPABASE_URL,
        SUPABASE_ANON_KEY: env.SUPABASE_ANON_KEY,
        SUPABASE_SERVICE_ROLE_KEY: env.SUPABASE_SERVICE_ROLE_KEY,
        PORT: "3000",
        NODE_ENV: "production",
      },
    });

    return container.fetch(request);
  },
};
