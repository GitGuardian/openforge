ALTER TABLE "skills" ADD COLUMN "updated_at" timestamptz DEFAULT now() NOT NULL;
--> statement-breakpoint
ALTER TABLE "skills" ADD COLUMN "status" text DEFAULT 'active' NOT NULL;
--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_registry_path" UNIQUE ("registry_id", "skill_md_path");
