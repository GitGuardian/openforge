FROM oven/bun:1 AS base

# git is required by the indexer (Bun.spawn git clone / git rev-parse)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json bun.lockb ./
RUN bun install --production --frozen-lockfile

COPY src/ src/
COPY public/ public/
COPY drizzle/ drizzle/
COPY drizzle.config.ts tsconfig.json ./

EXPOSE 3000

# Migrate on startup (idempotent — Drizzle skips already-applied migrations),
# then start the server. Safe with max_instances = 1.
CMD ["sh", "-c", "bun run db:migrate && bun run src/index.ts"]
