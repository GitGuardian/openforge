import {
  pgTable,
  uuid,
  text,
  timestamp,
  integer,
  smallint,
  boolean,
  jsonb,
  primaryKey,
  unique,
} from "drizzle-orm/pg-core";

// ---------------------------------------------------------------------------
// registries
// ---------------------------------------------------------------------------
export const registries = pgTable("registries", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull().unique(),
  gitUrl: text("git_url").notNull(),
  registryType: text("registry_type").notNull(), // "github" | "gitlab" | "local"
  webhookSecret: text("webhook_secret"),
  indexedAt: timestamp("indexed_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

// ---------------------------------------------------------------------------
// plugins
// ---------------------------------------------------------------------------
export const plugins = pgTable(
  "plugins",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    registryId: uuid("registry_id")
      .notNull()
      .references(() => registries.id),
    name: text("name").notNull(),
    version: text("version").notNull(),
    description: text("description").notNull(),
    category: text("category").notNull(),
    tags: text("tags").array().notNull(),
    readmeHtml: text("readme_html"),
    pluginJson: jsonb("plugin_json"),
    gitPath: text("git_path").notNull(),
    gitSha: text("git_sha").notNull(),
    status: text("status").notNull().default("approved"),
    installCount: integer("install_count").notNull().default(0),
    voteScore: integer("vote_score").notNull().default(0),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (table) => [unique("plugins_registry_name").on(table.registryId, table.name)],
);

// ---------------------------------------------------------------------------
// skills
// ---------------------------------------------------------------------------
export const skills = pgTable(
  "skills",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    pluginId: uuid("plugin_id").references(() => plugins.id),
    registryId: uuid("registry_id")
      .notNull()
      .references(() => registries.id),
    name: text("name").notNull(),
    description: text("description"),
    skillMdPath: text("skill_md_path").notNull(),
    metadata: jsonb("metadata"),
    status: text("status").notNull().default("active"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (table) => [unique("skills_registry_path").on(table.registryId, table.skillMdPath)],
);

// ---------------------------------------------------------------------------
// users
// ---------------------------------------------------------------------------
export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull().unique(),
  displayName: text("display_name"),
  role: text("role").notNull().default("user"), // "user" | "curator" | "admin"
  authId: uuid("auth_id").unique(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

// ---------------------------------------------------------------------------
// votes (composite PK: user_id + plugin_id)
// ---------------------------------------------------------------------------
export const votes = pgTable(
  "votes",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id),
    pluginId: uuid("plugin_id")
      .notNull()
      .references(() => plugins.id),
    value: smallint("value").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (table) => [primaryKey({ columns: [table.userId, table.pluginId] })],
);

// ---------------------------------------------------------------------------
// comments (self-referencing parent_id)
// ---------------------------------------------------------------------------
export const comments = pgTable("comments", {
  id: uuid("id").primaryKey().defaultRandom(),
  pluginId: uuid("plugin_id")
    .notNull()
    .references(() => plugins.id),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id),
  parentId: uuid("parent_id"),
  body: text("body").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
});

// ---------------------------------------------------------------------------
// install_events
// ---------------------------------------------------------------------------
export const installEvents = pgTable("install_events", {
  id: uuid("id").primaryKey().defaultRandom(),
  pluginName: text("plugin_name").notNull(),
  skillName: text("skill_name"),
  version: text("version"),
  source: text("source").notNull(),
  agents: text("agents").array().notNull(),
  cliVersion: text("cli_version"),
  isCi: boolean("is_ci").notNull().default(false),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

// ---------------------------------------------------------------------------
// allowed_domains
// ---------------------------------------------------------------------------
export const allowedDomains = pgTable("allowed_domains", {
  id: uuid("id").primaryKey().defaultRandom(),
  domain: text("domain").notNull().unique(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});
