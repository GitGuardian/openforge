-- ==========================================================================
-- Submissions table + RLS policies (Phase 5)
-- ==========================================================================

CREATE TABLE "submissions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"plugin_id" uuid,
	"user_id" uuid NOT NULL,
	"git_url" text NOT NULL,
	"description" text,
	"status" text DEFAULT 'pending' NOT NULL,
	"reviewer_id" uuid,
	"review_note" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"reviewed_at" timestamp with time zone
);
--> statement-breakpoint
ALTER TABLE "submissions" ADD CONSTRAINT "submissions_plugin_id_plugins_id_fk" FOREIGN KEY ("plugin_id") REFERENCES "public"."plugins"("id") ON DELETE no action ON UPDATE no action;
--> statement-breakpoint
ALTER TABLE "submissions" ADD CONSTRAINT "submissions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;
--> statement-breakpoint
ALTER TABLE "submissions" ADD CONSTRAINT "submissions_reviewer_id_users_id_fk" FOREIGN KEY ("reviewer_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;
--> statement-breakpoint

-- RLS: submissions
-- Users can read their own submissions; curators/admins can read all.
-- Users can insert their own submissions.
-- Curators/admins can update any submission (for review).
ALTER TABLE "submissions" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "submissions_select_own" ON "submissions" FOR SELECT USING (
  user_id = public.current_user_id()
  OR public.current_user_role() IN ('curator', 'admin')
);
--> statement-breakpoint
CREATE POLICY "submissions_insert_own" ON "submissions" FOR INSERT WITH CHECK (
  user_id = public.current_user_id()
);
--> statement-breakpoint
CREATE POLICY "submissions_update_curator" ON "submissions" FOR UPDATE USING (
  public.current_user_role() IN ('curator', 'admin')
);
--> statement-breakpoint
CREATE POLICY "submissions_delete_admin" ON "submissions" FOR DELETE USING (
  public.current_user_role() = 'admin'
);
