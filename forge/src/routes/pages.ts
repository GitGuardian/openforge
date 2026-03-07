import { Hono } from "hono";
import { html, raw } from "hono/html";
import { eq, ilike, or, and, desc, sql, count } from "drizzle-orm";
import { layout } from "../views/layout";
import { db } from "../db";
import { plugins, skills } from "../db/schema";
import type { AppEnv } from "../types";

export const pageRoutes = new Hono<AppEnv>();

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Helpers — render plugin cards and pagination
// ---------------------------------------------------------------------------

function pluginCard(plugin: {
  name: string;
  description: string;
  installCount: number;
  tags: string[];
}) {
  return html`
    <a
      href="/plugins/${plugin.name}"
      class="block p-4 bg-white rounded-lg border hover:border-blue-300 transition-colors"
    >
      <div class="flex justify-between items-start">
        <h3 class="text-lg font-semibold text-gray-900">${plugin.name}</h3>
        <span class="text-sm text-gray-500">${plugin.installCount} installs</span>
      </div>
      <p class="text-gray-600 mt-1">${plugin.description}</p>
      <div class="flex gap-2 mt-2">
        ${plugin.tags.map(
          (tag) =>
            html`<span class="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full"
              >${tag}</span
            >`
        )}
      </div>
    </a>
  `;
}

function paginationLinks(page: number, total: number, q: string) {
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const hasPrev = page > 0;
  const hasNext = page + 1 < totalPages;
  const qs = q ? `&q=${encodeURIComponent(q)}` : "";

  return html`
    <div class="flex justify-between items-center mt-6">
      ${hasPrev
        ? html`<a
            href="/?page=${page - 1}${raw(qs)}"
            class="text-sm text-blue-600 hover:text-blue-800"
            >&larr; Previous</a
          >`
        : html`<span></span>`}
      <span class="text-sm text-gray-500">
        Page ${page + 1} of ${Math.max(totalPages, 1)}
      </span>
      ${hasNext
        ? html`<a
            href="/?page=${page + 1}${raw(qs)}"
            class="text-sm text-blue-600 hover:text-blue-800"
            >Next &rarr;</a
          >`
        : html`<span></span>`}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Shared query logic — used by both the full page and the HTMX partial
// ---------------------------------------------------------------------------

async function queryPlugins(q: string, page: number) {
  const conditions = [eq(plugins.status, "approved")];
  if (q) {
    conditions.push(
      or(
        ilike(plugins.name, `%${q}%`),
        ilike(plugins.description, `%${q}%`)
      )!
    );
  }

  const where = and(...conditions);

  const [rows, [{ total }]] = await Promise.all([
    db
      .select()
      .from(plugins)
      .where(where)
      .orderBy(desc(plugins.installCount))
      .limit(PAGE_SIZE)
      .offset(page * PAGE_SIZE),
    db.select({ total: count() }).from(plugins).where(where),
  ]);

  return { rows, total };
}

// ---------------------------------------------------------------------------
// GET /partials/plugin-list — HTMX partial (no layout)
// ---------------------------------------------------------------------------

pageRoutes.get("/partials/plugin-list", async (c) => {
  const q = (c.req.query("q") ?? "").trim();
  const page = Math.max(0, parseInt(c.req.query("page") ?? "0", 10) || 0);

  const { rows, total } = await queryPlugins(q, page);

  return c.html(html`
    <div class="grid gap-4">
      ${rows.length > 0
        ? rows.map((p) => pluginCard(p))
        : html`<p class="text-gray-500 text-center py-8">
            No plugins found${q ? html` matching <strong>${q}</strong>` : ""}.
          </p>`}
    </div>
    ${paginationLinks(page, total, q)}
  `);
});

// ---------------------------------------------------------------------------
// GET / — Catalogue page (full page with layout)
// ---------------------------------------------------------------------------

pageRoutes.get("/", async (c) => {
  const user = c.get("user");
  const q = (c.req.query("q") ?? "").trim();
  const page = Math.max(0, parseInt(c.req.query("page") ?? "0", 10) || 0);

  const { rows, total } = await queryPlugins(q, page);

  const content = html`
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">Plugin Catalogue</h1>
      <p class="text-gray-600">
        Browse and discover plugins and skills for your AI agents.
      </p>
    </div>

    <div class="mb-6">
      <input
        hx-get="/partials/plugin-list"
        hx-trigger="input changed delay:300ms"
        hx-target="#plugin-list"
        hx-include="this"
        name="q"
        value="${q}"
        placeholder="Search plugins and skills..."
        class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
      />
    </div>

    <div id="plugin-list">
      <div class="grid gap-4">
        ${rows.length > 0
          ? rows.map((p) => pluginCard(p))
          : html`<p class="text-gray-500 text-center py-8">
              No plugins found${q ? html` matching <strong>${q}</strong>` : ""}.
            </p>`}
      </div>
      ${paginationLinks(page, total, q)}
    </div>
  `;

  return c.html(layout("Catalogue", content, user));
});

// ---------------------------------------------------------------------------
// GET /plugins/:name — Plugin detail page
// ---------------------------------------------------------------------------

pageRoutes.get("/plugins/:name", async (c) => {
  const user = c.get("user");
  const name = c.req.param("name");

  const [plugin] = await db
    .select()
    .from(plugins)
    .where(eq(plugins.name, name))
    .limit(1);

  if (!plugin) {
    const content = html`
      <div class="text-center py-16">
        <h1 class="text-2xl font-bold text-gray-900 mb-2">Plugin not found</h1>
        <p class="text-gray-600 mb-4">
          The plugin <strong>${name}</strong> does not exist.
        </p>
        <a href="/" class="text-blue-600 hover:text-blue-800">&larr; Back to catalogue</a>
      </div>
    `;
    return c.html(layout("Not Found", content, user), 404);
  }

  const pluginSkills = await db
    .select()
    .from(skills)
    .where(eq(skills.pluginId, plugin.id));

  const content = html`
    <div class="mb-6">
      <a href="/" class="text-blue-600 hover:text-blue-800 text-sm">&larr; Back to catalogue</a>
    </div>

    <div class="flex items-center gap-3 mb-4">
      <h1 class="text-3xl font-bold text-gray-900">${plugin.name}</h1>
      <span class="px-2 py-0.5 bg-gray-100 text-gray-700 text-sm rounded-full">
        v${plugin.version}
      </span>
    </div>

    <p class="text-gray-600 text-lg mb-4">${plugin.description}</p>

    <div class="flex flex-wrap gap-2 mb-8">
      ${plugin.tags.map(
        (tag) =>
          html`<span class="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full"
            >${tag}</span
          >`
      )}
    </div>

    <!-- Install instructions -->
    <div class="bg-gray-50 border rounded-lg p-6 mb-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-3">Install</h2>
      <div class="space-y-2 font-mono text-sm">
        <div class="flex gap-4">
          <span class="text-gray-500 w-28 shrink-0">CLI:</span>
          <code class="text-gray-900">uvx openforge add ${plugin.gitPath}</code>
        </div>
        <div class="flex gap-4">
          <span class="text-gray-500 w-28 shrink-0">Claude Code:</span>
          <span class="text-gray-900">Marketplace integration</span>
        </div>
        <div class="flex gap-4">
          <span class="text-gray-500 w-28 shrink-0">skills.sh:</span>
          <code class="text-gray-900">npx skills add ${plugin.gitPath}</code>
        </div>
      </div>
    </div>

    <!-- Skills list -->
    ${pluginSkills.length > 0
      ? html`
          <div class="mb-8">
            <h2 class="text-lg font-semibold text-gray-900 mb-3">Skills</h2>
            <div class="grid gap-3">
              ${pluginSkills.map(
                (s) => html`
                  <div class="p-3 bg-white border rounded-lg">
                    <h3 class="font-medium text-gray-900">${s.name}</h3>
                    ${s.description
                      ? html`<p class="text-gray-600 text-sm mt-1">${s.description}</p>`
                      : ""}
                  </div>
                `
              )}
            </div>
          </div>
        `
      : ""}

    <!-- Metadata -->
    <div class="mb-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-3">Metadata</h2>
      <dl class="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
        <dt class="text-gray-500">Category</dt>
        <dd class="text-gray-900">${plugin.category}</dd>
        <dt class="text-gray-500">Source</dt>
        <dd class="text-gray-900">${plugin.gitPath}</dd>
        <dt class="text-gray-500">Git SHA</dt>
        <dd class="text-gray-900 font-mono">${plugin.gitSha.slice(0, 12)}</dd>
        <dt class="text-gray-500">Status</dt>
        <dd class="text-gray-900">${plugin.status}</dd>
        <dt class="text-gray-500">Installs</dt>
        <dd class="text-gray-900">${plugin.installCount}</dd>
        <dt class="text-gray-500">Votes</dt>
        <dd class="text-gray-900">${plugin.voteScore}</dd>
      </dl>
    </div>

    <!-- README -->
    ${plugin.readmeHtml
      ? html`
          <div class="mb-8">
            <h2 class="text-lg font-semibold text-gray-900 mb-3">README</h2>
            <div class="prose max-w-none bg-white border rounded-lg p-6">
              ${raw(plugin.readmeHtml)}
            </div>
          </div>
        `
      : ""}
  `;

  return c.html(layout(plugin.name, content, user));
});
