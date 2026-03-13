import { describe, expect, test, spyOn } from "bun:test";
import { mkdtemp, writeFile, mkdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

// ---------------------------------------------------------------------------
// Import the indexer functions directly (no mocking needed for pure functions)
// ---------------------------------------------------------------------------

const { getHeadSha, findFiles, parseFrontmatter, parsePlugin, parseMarketplace } =
  await import("../../src/lib/indexer");

// ---------------------------------------------------------------------------
// Tests: getHeadSha
// ---------------------------------------------------------------------------

describe("getHeadSha", () => {
  test("throws on git failure instead of returning 'unknown'", async () => {
    // /tmp exists but is not a git repo, so git rev-parse HEAD will fail with non-zero exit
    const result = getHeadSha("/tmp");
    await expect(result).rejects.toThrow();
  });

  test("returns SHA string on success in a real git repo", async () => {
    const sha = await getHeadSha("/Users/jeremy.brown/dev/openforge");
    expect(sha).toMatch(/^[0-9a-f]{40}$/);
  });
});

// ---------------------------------------------------------------------------
// Tests: findFiles
// ---------------------------------------------------------------------------

describe("findFiles", () => {
  test("logs warning when readdir fails on nonexistent path", async () => {
    const warnSpy = spyOn(console, "warn").mockImplementation(() => {});
    const results = await findFiles("/nonexistent/path/that/does/not/exist", /\.json$/);
    expect(results).toEqual([]);
    expect(warnSpy).toHaveBeenCalled();
    const warnMsg = warnSpy.mock.calls[0]?.[0];
    expect(warnMsg).toContain("readdir failed");
    warnSpy.mockRestore();
  });

  test("returns empty array when readdir fails", async () => {
    const warnSpy = spyOn(console, "warn").mockImplementation(() => {});
    const results = await findFiles("/nonexistent/path", /\.json$/);
    expect(results).toEqual([]);
    warnSpy.mockRestore();
  });

  test("finds files matching pattern in directory tree", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      await mkdir(join(tmpDir, "sub"), { recursive: true });
      await writeFile(join(tmpDir, "plugin.json"), "{}");
      await writeFile(join(tmpDir, "sub", "plugin.json"), "{}");
      await writeFile(join(tmpDir, "README.md"), "# Hi");

      const results = await findFiles(tmpDir, /^plugin\.json$/);
      expect(results).toHaveLength(2);
      expect(results.every((r: string) => r.endsWith("plugin.json"))).toBe(true);
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  test("skips hidden directories and node_modules", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      await mkdir(join(tmpDir, ".hidden"), { recursive: true });
      await mkdir(join(tmpDir, "node_modules"), { recursive: true });
      await writeFile(join(tmpDir, ".hidden", "plugin.json"), "{}");
      await writeFile(join(tmpDir, "node_modules", "plugin.json"), "{}");
      await writeFile(join(tmpDir, "plugin.json"), "{}");

      const results = await findFiles(tmpDir, /^plugin\.json$/);
      expect(results).toHaveLength(1);
      expect(results[0]).toBe(join(tmpDir, "plugin.json"));
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });
});

// ---------------------------------------------------------------------------
// Tests: parseFrontmatter
// ---------------------------------------------------------------------------

describe("parseFrontmatter", () => {
  test("parses name, description, and inline tags", () => {
    const content = `---
name: my-skill
description: A test skill
tags: [coding, testing]
---

Body content here.
`;
    const result = parseFrontmatter(content);
    expect(result.name).toBe("my-skill");
    expect(result.description).toBe("A test skill");
    expect(result.tags).toEqual(["coding", "testing"]);
  });

  test("parses multi-line tag list", () => {
    const content = `---
name: another-skill
description: Another skill
tags:
  - tag-a
  - tag-b
---
`;
    const result = parseFrontmatter(content);
    expect(result.tags).toEqual(["tag-a", "tag-b"]);
  });

  test("returns empty defaults when no frontmatter", () => {
    const result = parseFrontmatter("No frontmatter here.");
    expect(result.name).toBe("");
    expect(result.description).toBe("");
    expect(result.tags).toEqual([]);
  });

  test("strips quotes from values", () => {
    const content = `---
name: "quoted-name"
description: 'single-quoted'
tags: ["a", 'b']
---
`;
    const result = parseFrontmatter(content);
    expect(result.name).toBe("quoted-name");
    expect(result.description).toBe("single-quoted");
    expect(result.tags).toEqual(["a", "b"]);
  });
});

// ---------------------------------------------------------------------------
// Tests: parsePlugin
// ---------------------------------------------------------------------------

describe("parsePlugin", () => {
  test("parses a valid plugin.json", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      const pluginDir = join(tmpDir, "my-plugin");
      await mkdir(pluginDir, { recursive: true });
      await writeFile(
        join(pluginDir, "plugin.json"),
        JSON.stringify({
          name: "test-plugin",
          description: "A test plugin",
          version: "2.0.0",
          category: "tools",
          tags: ["testing"],
        }),
      );

      const result = await parsePlugin(join(pluginDir, "plugin.json"), tmpDir);
      expect(result).not.toBeNull();
      expect(result!.name).toBe("test-plugin");
      expect(result!.description).toBe("A test plugin");
      expect(result!.version).toBe("2.0.0");
      expect(result!.category).toBe("tools");
      expect(result!.tags).toEqual(["testing"]);
      expect(result!.gitPath).toBe("my-plugin");
      expect(result!.readmeHtml).toBeNull();
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  test("reads README.md if present", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      await writeFile(
        join(tmpDir, "plugin.json"),
        JSON.stringify({ name: "with-readme" }),
      );
      await writeFile(join(tmpDir, "README.md"), "# Hello\n\nWorld");

      const result = await parsePlugin(join(tmpDir, "plugin.json"), tmpDir);
      expect(result).not.toBeNull();
      expect(result!.readmeHtml).toContain("<h1>");
      expect(result!.readmeHtml).toContain("Hello");
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  test("uses defaults for missing fields", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      await writeFile(join(tmpDir, "plugin.json"), "{}");

      const result = await parsePlugin(join(tmpDir, "plugin.json"), tmpDir);
      expect(result).not.toBeNull();
      // Name defaults to directory basename
      expect(result!.version).toBe("1.0.0");
      expect(result!.category).toBe("uncategorized");
      expect(result!.tags).toEqual([]);
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  test("returns null for invalid JSON", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      const warnSpy = spyOn(console, "warn").mockImplementation(() => {});
      await writeFile(join(tmpDir, "plugin.json"), "not json");

      const result = await parsePlugin(join(tmpDir, "plugin.json"), tmpDir);
      expect(result).toBeNull();
      warnSpy.mockRestore();
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });
});

// ---------------------------------------------------------------------------
// Tests: parseMarketplace
// ---------------------------------------------------------------------------

describe("parseMarketplace", () => {
  test("parses marketplace.json with packages array", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      const marketplace = {
        packages: [
          { name: "pkg-a", description: "Package A", version: "1.0.0", tags: ["a"] },
          { name: "pkg-b", description: "Package B" },
        ],
      };
      const mpPath = join(tmpDir, "marketplace.json");
      await writeFile(mpPath, JSON.stringify(marketplace));

      const results = await parseMarketplace(mpPath, tmpDir);
      expect(results).toHaveLength(2);
      expect(results[0].name).toBe("pkg-a");
      expect(results[0].tags).toEqual(["a"]);
      expect(results[1].name).toBe("pkg-b");
      expect(results[1].version).toBe("1.0.0");
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  test("returns empty array for invalid marketplace JSON", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      const warnSpy = spyOn(console, "warn").mockImplementation(() => {});
      await writeFile(join(tmpDir, "marketplace.json"), "bad json");

      const results = await parseMarketplace(join(tmpDir, "marketplace.json"), tmpDir);
      expect(results).toEqual([]);
      warnSpy.mockRestore();
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });

  test("handles missing packages key", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "indexer-test-"));
    try {
      await writeFile(join(tmpDir, "marketplace.json"), JSON.stringify({ version: 1 }));

      const results = await parseMarketplace(join(tmpDir, "marketplace.json"), tmpDir);
      expect(results).toEqual([]);
    } finally {
      await rm(tmpDir, { recursive: true, force: true });
    }
  });
});
