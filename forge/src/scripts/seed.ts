/**
 * Seed script — populate the database from a git repository.
 *
 * Usage:
 *   bun run seed -- --repo https://github.com/owner/repo.git --name my-registry
 *
 * Thin CLI wrapper around the indexer library. Upserts the registry record,
 * then delegates scanning and upserting to indexRegistry().
 */

import { db } from "../db";
import { registries } from "../db/schema";
import { indexRegistry } from "../lib/indexer";

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

function parseArgs(argv: string[]): { repo: string; name: string } {
  let repo = "";
  let name = "";

  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--repo" && argv[i + 1]) {
      repo = argv[i + 1];
      i++;
    } else if (argv[i] === "--name" && argv[i + 1]) {
      name = argv[i + 1];
      i++;
    }
  }

  if (!repo) {
    console.error("Usage: bun run seed -- --repo <git-url> [--name <registry-name>]");
    process.exit(1);
  }

  // Derive name from URL if not provided: https://github.com/owner/repo.git → owner/repo
  if (!name) {
    const match = repo.match(/([^/]+\/[^/]+?)(?:\.git)?$/);
    name = match ? match[1] : repo;
  }

  return { repo, name };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const { repo, name } = parseArgs(process.argv.slice(2));

  // Upsert registry (CLI-specific — webhook handler looks up by ID instead)
  const [registry] = await db
    .insert(registries)
    .values({
      name,
      gitUrl: repo,
      registryType: "github",
    })
    .onConflictDoUpdate({
      target: registries.name,
      set: { gitUrl: repo },
    })
    .returning();

  console.log(`Registry "${name}" → ${registry.id}`);

  // Delegate to indexer
  const result = await indexRegistry(registry.id);

  console.log("\n--- Seed Summary ---");
  console.log(`Registry:  ${name} (${repo})`);
  console.log(`Plugins:   ${result.pluginsFound} indexed`);
  console.log(`Skills:    ${result.skillsFound} indexed`);
  if (result.pluginsRemoved > 0 || result.skillsRemoved > 0) {
    console.log(`Removed:   ${result.pluginsRemoved} plugins, ${result.skillsRemoved} skills`);
  }
  if (result.errors.length > 0) {
    console.error(`Errors:    ${result.errors.join(", ")}`);
  }
  console.log("Done.");
  process.exit(0);
}

main().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
