/**
 * Seed script — populate the database from a git repository.
 *
 * Usage:
 *   bun run seed -- --repo https://github.com/owner/repo.git --name my-registry
 *
 * The script clones the repo, scans for plugin.json files, marketplace.json,
 * and SKILL.md files, then upserts everything into the database.
 */

import { readdir, readFile, rm, mkdtemp } from "node:fs/promises";
import { join, dirname, relative, basename } from "node:path";
import { tmpdir } from "node:os";
import { eq, and } from "drizzle-orm";
import { db } from "../db";
import { plugins, skills, registries } from "../db/schema";
import { renderMarkdown } from "../lib/markdown";

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
// Git clone
// ---------------------------------------------------------------------------

async function cloneRepo(url: string): Promise<string> {
  const tmpDir = await mkdtemp(join(tmpdir(), "openforge-seed-"));
  console.log(`Cloning ${url} into ${tmpDir}...`);

  const proc = Bun.spawn(["git", "clone", "--depth", "1", url, tmpDir], {
    stdout: "inherit",
    stderr: "inherit",
  });

  const exitCode = await proc.exited;
  if (exitCode !== 0) {
    throw new Error(`git clone failed with exit code ${exitCode}`);
  }

  return tmpDir;
}

// ---------------------------------------------------------------------------
// Get HEAD SHA
// ---------------------------------------------------------------------------

async function getHeadSha(repoDir: string): Promise<string> {
  const proc = Bun.spawn(["git", "rev-parse", "HEAD"], {
    cwd: repoDir,
    stdout: "pipe",
    stderr: "pipe",
  });

  const output = await new Response(proc.stdout).text();
  const exitCode = await proc.exited;
  if (exitCode !== 0) {
    return "unknown";
  }
  return output.trim();
}

// ---------------------------------------------------------------------------
// Recursive file scanning
// ---------------------------------------------------------------------------

async function findFiles(
  dir: string,
  pattern: RegExp,
  results: string[] = [],
): Promise<string[]> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return results;
  }

  for (const entry of entries) {
    const fullPath = join(dir, entry.name);

    // Skip hidden directories and node_modules
    if (entry.name.startsWith(".") && entry.isDirectory()) continue;
    if (entry.name === "node_modules") continue;

    if (entry.isDirectory()) {
      await findFiles(fullPath, pattern, results);
    } else if (pattern.test(entry.name)) {
      results.push(fullPath);
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// YAML frontmatter parsing (minimal, no yaml dependency)
// ---------------------------------------------------------------------------

interface SkillFrontmatter {
  name: string;
  description: string;
  tags: string[];
}

function parseFrontmatter(content: string): SkillFrontmatter {
  const result: SkillFrontmatter = { name: "", description: "", tags: [] };

  const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!fmMatch) return result;

  const block = fmMatch[1];

  // name: value
  const nameMatch = block.match(/^name:\s*(.+)$/m);
  if (nameMatch) result.name = nameMatch[1].trim().replace(/^["']|["']$/g, "");

  // description: value
  const descMatch = block.match(/^description:\s*(.+)$/m);
  if (descMatch) result.description = descMatch[1].trim().replace(/^["']|["']$/g, "");

  // tags: [tag1, tag2] or tags:\n  - tag1\n  - tag2
  const inlineTagsMatch = block.match(/^tags:\s*\[([^\]]*)\]/m);
  if (inlineTagsMatch) {
    result.tags = inlineTagsMatch[1]
      .split(",")
      .map((t) => t.trim().replace(/^["']|["']$/g, ""))
      .filter(Boolean);
  } else {
    // Multi-line list form
    const tagsSection = block.match(/^tags:\s*\n((?:\s+-\s+.+\n?)*)/m);
    if (tagsSection) {
      result.tags = tagsSection[1]
        .split("\n")
        .map((line) => {
          const m = line.match(/^\s+-\s+(.+)/);
          return m ? m[1].trim().replace(/^["']|["']$/g, "") : "";
        })
        .filter(Boolean);
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Plugin JSON parsing
// ---------------------------------------------------------------------------

interface PluginData {
  name: string;
  description: string;
  version: string;
  category: string;
  tags: string[];
  pluginJson: Record<string, unknown>;
  gitPath: string;
  readmeHtml: string | null;
}

async function parsePlugin(
  pluginJsonPath: string,
  repoRoot: string,
): Promise<PluginData | null> {
  try {
    const raw = await readFile(pluginJsonPath, "utf-8");
    const data = JSON.parse(raw) as Record<string, unknown>;

    const pluginDir = dirname(pluginJsonPath);
    const gitPath = relative(repoRoot, pluginDir) || ".";

    const name =
      typeof data.name === "string" ? data.name : basename(pluginDir);
    const description =
      typeof data.description === "string" ? data.description : "";
    const version =
      typeof data.version === "string" ? data.version : "1.0.0";
    const category =
      typeof data.category === "string" ? data.category : "uncategorized";
    const tags = Array.isArray(data.tags)
      ? (data.tags as unknown[]).filter((t): t is string => typeof t === "string")
      : [];

    // Look for README.md in the plugin directory
    let readmeHtml: string | null = null;
    try {
      const readmePath = join(pluginDir, "README.md");
      const readmeContent = await readFile(readmePath, "utf-8");
      readmeHtml = renderMarkdown(readmeContent);
    } catch {
      // No README — that's fine
    }

    return {
      name,
      description,
      version,
      category,
      tags,
      pluginJson: data,
      gitPath,
      readmeHtml,
    };
  } catch (err) {
    console.warn(`Failed to parse ${pluginJsonPath}:`, err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Marketplace JSON parsing
// ---------------------------------------------------------------------------

async function parseMarketplace(
  marketplacePath: string,
  repoRoot: string,
): Promise<PluginData[]> {
  const results: PluginData[] = [];

  try {
    const raw = await readFile(marketplacePath, "utf-8");
    const data = JSON.parse(raw) as Record<string, unknown>;
    const packages = Array.isArray(data.packages) ? data.packages : [];

    for (const pkg of packages) {
      if (typeof pkg !== "object" || pkg === null) continue;
      const p = pkg as Record<string, unknown>;

      results.push({
        name: typeof p.name === "string" ? p.name : "unknown",
        description: typeof p.description === "string" ? p.description : "",
        version: typeof p.version === "string" ? p.version : "1.0.0",
        category: typeof p.category === "string" ? p.category : "uncategorized",
        tags: Array.isArray(p.tags)
          ? (p.tags as unknown[]).filter((t): t is string => typeof t === "string")
          : [],
        pluginJson: p,
        gitPath: typeof p.gitPath === "string" ? p.gitPath : ".",
        readmeHtml: null,
      });
    }
  } catch (err) {
    console.warn(`Failed to parse ${marketplacePath}:`, err);
  }

  return results;
}

// ---------------------------------------------------------------------------
// Main seed logic
// ---------------------------------------------------------------------------

async function main() {
  const { repo, name } = parseArgs(process.argv.slice(2));

  // 1. Clone the repo
  const repoDir = await cloneRepo(repo);

  try {
    const sha = await getHeadSha(repoDir);

    // 2. Upsert registry
    const [registry] = await db
      .insert(registries)
      .values({
        name,
        gitUrl: repo,
        registryType: "github",
        indexedAt: new Date(),
      })
      .onConflictDoUpdate({
        target: registries.name,
        set: {
          gitUrl: repo,
          indexedAt: new Date(),
        },
      })
      .returning();

    const registryId = registry.id;
    console.log(`Registry "${name}" → ${registryId}`);

    // 3. Scan for content
    const pluginJsonFiles = await findFiles(repoDir, /^plugin\.json$/);
    const marketplaceFiles = await findFiles(repoDir, /^marketplace\.json$/);
    const skillMdFiles = await findFiles(repoDir, /^SKILL\.md$/i);

    // Also look inside .claude-plugin directories
    const claudePluginDirs = await findFiles(repoDir, /^\.claude-plugin$/);
    // .claude-plugin is a directory name, but findFiles finds files. Scan manually.
    const allPluginJsonPaths = new Set(pluginJsonFiles);
    try {
      const claudePluginFiles = await findFiles(repoDir, /^plugin\.json$/);
      for (const f of claudePluginFiles) {
        allPluginJsonPaths.add(f);
      }
    } catch {
      // ignore
    }

    // 4. Parse and upsert plugins
    const pluginDataList: PluginData[] = [];

    for (const pjPath of allPluginJsonPaths) {
      const data = await parsePlugin(pjPath, repoDir);
      if (data) pluginDataList.push(data);
    }

    // Parse marketplace.json files (usually at root)
    for (const mpPath of marketplaceFiles) {
      const entries = await parseMarketplace(mpPath, repoDir);
      pluginDataList.push(...entries);
    }

    // Deduplicate by name (prefer plugin.json over marketplace.json)
    const pluginsByName = new Map<string, PluginData>();
    for (const pd of pluginDataList) {
      if (!pluginsByName.has(pd.name)) {
        pluginsByName.set(pd.name, pd);
      }
    }

    let pluginsUpserted = 0;
    // Map of gitPath → plugin DB id, for linking skills
    const pluginIdByPath = new Map<string, string>();

    for (const pd of pluginsByName.values()) {
      const [row] = await db
        .insert(plugins)
        .values({
          registryId,
          name: pd.name,
          version: pd.version,
          description: pd.description,
          category: pd.category,
          tags: pd.tags,
          readmeHtml: pd.readmeHtml,
          pluginJson: pd.pluginJson,
          gitPath: pd.gitPath,
          gitSha: sha,
          status: "approved",
        })
        .onConflictDoUpdate({
          target: [plugins.registryId, plugins.name],
          set: {
            version: pd.version,
            description: pd.description,
            category: pd.category,
            tags: pd.tags,
            readmeHtml: pd.readmeHtml,
            pluginJson: pd.pluginJson,
            gitPath: pd.gitPath,
            gitSha: sha,
            updatedAt: new Date(),
          },
        })
        .returning();

      pluginIdByPath.set(pd.gitPath, row.id);
      pluginsUpserted++;
    }

    // 5. Parse and upsert skills
    let skillsUpserted = 0;

    for (const skillPath of skillMdFiles) {
      const content = await readFile(skillPath, "utf-8");
      const fm = parseFrontmatter(content);
      const relPath = relative(repoDir, skillPath);

      // Derive name from frontmatter or directory
      const skillName = fm.name || basename(dirname(skillPath));

      // Determine if this skill belongs to a plugin
      // Walk up from the skill to see if any parent has a plugin.json
      let pluginId: string | null = null;
      let checkDir = dirname(skillPath);
      while (checkDir.startsWith(repoDir) && checkDir !== repoDir) {
        const checkPath = relative(repoDir, checkDir);
        if (pluginIdByPath.has(checkPath)) {
          pluginId = pluginIdByPath.get(checkPath) ?? null;
          break;
        }
        checkDir = dirname(checkDir);
      }
      // Also check root (".")
      if (!pluginId && pluginIdByPath.has(".")) {
        pluginId = pluginIdByPath.get(".") ?? null;
      }

      // Upsert skill — since skills table has no unique constraint beyond id,
      // we do a select + insert/update
      const existing = await db
        .select({ id: skills.id })
        .from(skills)
        .where(
          and(
            eq(skills.registryId, registryId),
            eq(skills.skillMdPath, relPath),
          ),
        )
        .limit(1);

      if (existing.length > 0) {
        await db
          .update(skills)
          .set({
            name: skillName,
            description: fm.description || null,
            pluginId,
            metadata: fm.tags.length > 0 ? { tags: fm.tags } : null,
          })
          .where(eq(skills.id, existing[0].id));
      } else {
        await db.insert(skills).values({
          registryId,
          pluginId,
          name: skillName,
          description: fm.description || null,
          skillMdPath: relPath,
          metadata: fm.tags.length > 0 ? { tags: fm.tags } : null,
        });
      }

      skillsUpserted++;
    }

    // 6. Summary
    console.log("\n--- Seed Summary ---");
    console.log(`Registry:  ${name} (${repo})`);
    console.log(`SHA:       ${sha}`);
    console.log(`Plugins:   ${pluginsUpserted} upserted`);
    console.log(`Skills:    ${skillsUpserted} upserted`);
    console.log("Done.");
  } finally {
    // 7. Clean up temp directory
    console.log("Cleaning up...");
    await rm(repoDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
