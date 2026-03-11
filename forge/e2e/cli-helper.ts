/**
 * CLI spawn helper for cross-component E2E tests.
 *
 * Uses spawnSync with an explicit args array — never shell string interpolation.
 * CLI working directory is cli/ so uv can resolve pyproject.toml.
 * Token isolation: XDG_CONFIG_HOME is set per-test to a temp dir.
 */

import { spawnSync } from "child_process";
import { resolve } from "path";

/** Absolute path to the cli/ directory (one level up from forge/, one more up from e2e/) */
export const CLI_DIR = resolve(__dirname, "../../cli");

export interface CLIResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

/**
 * Run an openforge CLI command as a subprocess.
 *
 * @param args - CLI subcommands + arguments, e.g. ['auth', 'login'] or ['publish', 'https://...']
 * @param env  - Additional env vars merged into the subprocess environment
 * @param input - Optional stdin string (for interactive prompts)
 */
export function runCLI(
  args: string[],
  env: Record<string, string> = {},
  input?: string,
): CLIResult {
  const result = spawnSync("uv", ["run", "openforge", ...args], {
    cwd: CLI_DIR,
    env: {
      ...process.env,
      OPENFORGE_FORGE_URL: "http://localhost:3000",
      OPENFORGE_SUPABASE_URL:
        process.env.SUPABASE_URL || "http://127.0.0.1:54321",
      ...env,
    },
    input,
    encoding: "utf-8",
    timeout: 30_000,
  });

  return {
    exitCode: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

/**
 * Log in via the CLI non-interactively by piping email + password to stdin.
 * Token is stored in XDG_CONFIG_HOME/openforge/token.json.
 */
export function cliLogin(
  email: string,
  password: string,
  xdgConfigHome: string,
): CLIResult {
  return runCLI(
    ["auth", "login"],
    { XDG_CONFIG_HOME: xdgConfigHome },
    `${email}\n${password}\n`,
  );
}

/**
 * Submit a plugin via the CLI.
 * Requires prior login (token in xdgConfigHome/openforge/token.json).
 */
export function cliPublish(
  gitUrl: string,
  description: string,
  xdgConfigHome: string,
): CLIResult {
  return runCLI(
    ["publish", gitUrl, "--description", description],
    { XDG_CONFIG_HOME: xdgConfigHome },
  );
}
