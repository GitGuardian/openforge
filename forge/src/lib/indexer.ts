/**
 * Indexer library — reusable functions for scanning git repos and upserting
 * plugins/skills into the database. Used by the seed script and webhook handler.
 */

import { readdir, readFile, rm, mkdtemp } from "node:fs/promises";
import { join, dirname, relative, basename } from "node:path";
import { tmpdir } from "node:os";
import { eq, and, ne, notInArray } from "drizzle-orm";
import { db } from "../db";
import { plugins, skills, registries, submissions } from "../db/schema";
import { renderMarkdown } from "./markdown";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SkillFrontmatter {
  name: string;
  description: string;
  tags: string[];
}

export interface PluginData {
  name: string;
  description: string;
  version: string;
  category: string;
  tags: string[];
  pluginJson: Record<string, unknown>;
  gitPath: string;
  readmeHtml: string | null;
}

export interface IndexResult {
  pluginsFound: number;
  skillsFound: number;
  pluginsRemoved: number;
  skillsRemoved: number;
  errors: string[];
}

// ---------------------------------------------------------------------------
// Git operations
// ---------------------------------------------------------------------------

export async function cloneRepo(url: string): Promise<string> {
  const tmpDir = await mkdtemp(join(tmpdir(), "openforge-index-"));
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

export async function getHeadSha(repoDir: string): Promise<string> {
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
// File scanning
// ---------------------------------------------------------------------------

export async function findFiles(
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
// Parsing
// ---------------------------------------------------------------------------

export function parseFrontmatter(content: string): SkillFrontmatter {
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

export async function parsePlugin(
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

export async function parseMarketplace(
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
// Main indexing entry point
// ---------------------------------------------------------------------------

/**
 * Index a registry by its database ID. Clones the git repo, scans for
 * plugins and skills, upserts into the database, and marks stale content
 * as removed.
 */
export async function indexRegistry(registryId: string): Promise<IndexResult> {
  const result: IndexResult = {
    pluginsFound: 0,
    skillsFound: 0,
    pluginsRemoved: 0,
    skillsRemoved: 0,
    errors: [],
  };

  // 1. Look up registry
  const [registry] = await db
    .select()
    .from(registries)
    .where(eq(registries.id, registryId))
    .limit(1);

  if (!registry) {
    result.errors.push(`Registry ${registryId} not found`);
    return result;
  }

  // 2. Clone repo
  let repoDir: string;
  try {
    repoDir = await cloneRepo(registry.gitUrl);
  } catch (err) {
    result.errors.push(`Clone failed: ${err instanceof Error ? err.message : String(err)}`);
    return result;
  }

  try {
    // 3. Get HEAD SHA
    const sha = await getHeadSha(repoDir);

    // 4. Scan for content
    const pluginJsonFiles = await findFiles(repoDir, /^plugin\.json$/);
    const marketplaceFiles = await findFiles(repoDir, /^marketplace\.json$/);
    const skillMdFiles = await findFiles(repoDir, /^SKILL\.md$/i);

    // Collect all plugin.json paths (deduplicates via Set)
    const allPluginJsonPaths = new Set(pluginJsonFiles);

    // 5. Parse plugins
    const pluginDataList: PluginData[] = [];

    for (const pjPath of allPluginJsonPaths) {
      const data = await parsePlugin(pjPath, repoDir);
      if (data) pluginDataList.push(data);
    }

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

    // 6. Upsert plugins
    const pluginIdByPath = new Map<string, string>();

    for (const pd of pluginsByName.values()) {
      try {
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
              status: "approved",
              updatedAt: new Date(),
            },
          })
          .returning();

        pluginIdByPath.set(pd.gitPath, row.id);
        result.pluginsFound++;
      } catch (err) {
        result.errors.push(`Plugin upsert failed for ${pd.name}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }

    // 7. Upsert skills (now using ON CONFLICT with unique constraint)
    const foundSkillPaths: string[] = [];

    for (const skillPath of skillMdFiles) {
      const content = await readFile(skillPath, "utf-8");
      const fm = parseFrontmatter(content);
      const relPath = relative(repoDir, skillPath);
      foundSkillPaths.push(relPath);

      const skillName = fm.name || basename(dirname(skillPath));

      // Determine parent plugin by walking up directories
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
      if (!pluginId && pluginIdByPath.has(".")) {
        pluginId = pluginIdByPath.get(".") ?? null;
      }

      const metadata = fm.tags.length > 0 ? { tags: fm.tags } : null;

      try {
        await db
          .insert(skills)
          .values({
            registryId,
            pluginId,
            name: skillName,
            description: fm.description || null,
            skillMdPath: relPath,
            metadata,
            status: "active",
            updatedAt: new Date(),
          })
          .onConflictDoUpdate({
            target: [skills.registryId, skills.skillMdPath],
            set: {
              name: skillName,
              description: fm.description || null,
              pluginId,
              metadata,
              status: "active",
              updatedAt: new Date(),
            },
          });

        result.skillsFound++;
      } catch (err) {
        result.errors.push(`Skill upsert failed for ${relPath}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }

    // 8. Detect stale content — mark plugins/skills not found in this scan as 'removed'
    const foundPluginNames = [...pluginsByName.keys()];

    if (foundPluginNames.length > 0) {
      const removedPlugins = await db
        .update(plugins)
        .set({ status: "removed", updatedAt: new Date() })
        .where(
          and(
            eq(plugins.registryId, registryId),
            notInArray(plugins.name, foundPluginNames),
            ne(plugins.status, "removed"),
          ),
        )
        .returning({ id: plugins.id });
      result.pluginsRemoved = removedPlugins.length;
    }

    if (foundSkillPaths.length > 0) {
      const removedSkills = await db
        .update(skills)
        .set({ status: "removed", updatedAt: new Date() })
        .where(
          and(
            eq(skills.registryId, registryId),
            notInArray(skills.skillMdPath, foundSkillPaths),
            ne(skills.status, "removed"),
          ),
        )
        .returning({ id: skills.id });
      result.skillsRemoved = removedSkills.length;
    }

    // 9. Update registries.indexed_at
    await db
      .update(registries)
      .set({ indexedAt: new Date() })
      .where(eq(registries.id, registryId));
  } finally {
    // 10. Cleanup temp directory
    console.log("Cleaning up...");
    await rm(repoDir, { recursive: true, force: true });
  }

  return result;
}

// ---------------------------------------------------------------------------
// Submission indexing — validate and extract plugin from a submitted repo
// ---------------------------------------------------------------------------

/**
 * Index a submission: clone the repo, scan for plugins, and either link the
 * found plugin (with "pending" status) or auto-reject the submission.
 */
export async function indexSubmission(submissionId: string): Promise<void> {
  // 1. Look up the submission
  const [submission] = await db
    .select()
    .from(submissions)
    .where(eq(submissions.id, submissionId))
    .limit(1);

  if (!submission || submission.status !== "pending") return;

  // 2. Create or reuse a registry for this git URL
  const normalize = (url: string) => url.replace(/\.git$/, "").replace(/\/$/, "");
  const normalizedUrl = normalize(submission.gitUrl);

  const allRegs = await db.select().from(registries);
  let registry = allRegs.find((r) => normalize(r.gitUrl) === normalizedUrl);

  if (!registry) {
    const [newReg] = await db
      .insert(registries)
      .values({
        name: `submission-${submissionId.slice(0, 8)}`,
        gitUrl: submission.gitUrl,
        registryType: "github",
      })
      .returning();
    registry = newReg;
  }

  // 3. Clone the repo
  let repoDir: string;
  try {
    repoDir = await cloneRepo(submission.gitUrl);
  } catch (err) {
    await rejectSubmission(submissionId, `Failed to clone repository: ${err instanceof Error ? err.message : String(err)}`);
    return;
  }

  try {
    const sha = await getHeadSha(repoDir);

    // 4. Scan for plugin.json and marketplace.json
    const pluginJsonFiles = await findFiles(repoDir, /^plugin\.json$/);
    const marketplaceFiles = await findFiles(repoDir, /^marketplace\.json$/);

    const pluginDataList: PluginData[] = [];
    for (const pjPath of pluginJsonFiles) {
      const data = await parsePlugin(pjPath, repoDir);
      if (data) pluginDataList.push(data);
    }
    for (const mpPath of marketplaceFiles) {
      const entries = await parseMarketplace(mpPath, repoDir);
      pluginDataList.push(...entries);
    }

    if (pluginDataList.length === 0) {
      await rejectSubmission(submissionId, "No plugin.json or marketplace.json found in repository.");
      return;
    }

    // 5. Use the first plugin found and create it with "pending" status
    const pd = pluginDataList[0];
    const [pluginRow] = await db
      .insert(plugins)
      .values({
        registryId: registry.id,
        name: pd.name,
        version: pd.version,
        description: pd.description,
        category: pd.category,
        tags: pd.tags,
        readmeHtml: pd.readmeHtml,
        pluginJson: pd.pluginJson,
        gitPath: pd.gitPath,
        gitSha: sha,
        status: "pending",
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
          status: "pending",
          updatedAt: new Date(),
        },
      })
      .returning();

    // 6. Link the plugin to the submission
    await db
      .update(submissions)
      .set({ pluginId: pluginRow.id })
      .where(eq(submissions.id, submissionId));
  } catch (err) {
    await rejectSubmission(submissionId, `Indexing failed: ${err instanceof Error ? err.message : String(err)}`);
  } finally {
    await rm(repoDir, { recursive: true, force: true });
  }
}

async function rejectSubmission(submissionId: string, reason: string): Promise<void> {
  await db
    .update(submissions)
    .set({
      status: "rejected",
      reviewNote: reason,
      reviewedAt: new Date(),
    })
    .where(eq(submissions.id, submissionId));
}
