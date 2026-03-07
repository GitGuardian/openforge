-- ==========================================================================
-- RLS Policies for OpenForge
-- ==========================================================================
-- The Forge app uses the service role key for write operations (seeding,
-- indexing), which bypasses RLS. These policies protect against direct
-- Supabase client access and future public API usage.
-- ==========================================================================

-- Helper function: get the app-level role for the current auth user
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT role FROM public.users WHERE auth_id = auth.uid();
$$;
--> statement-breakpoint

-- Helper function: get the app-level user ID for the current auth user
CREATE OR REPLACE FUNCTION public.current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT id FROM public.users WHERE auth_id = auth.uid();
$$;
--> statement-breakpoint

-- registries: public read, admin write
ALTER TABLE "registries" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "registries_select" ON "registries" FOR SELECT USING (true);
--> statement-breakpoint
CREATE POLICY "registries_admin_insert" ON "registries" FOR INSERT WITH CHECK (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "registries_admin_update" ON "registries" FOR UPDATE USING (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "registries_admin_delete" ON "registries" FOR DELETE USING (public.current_user_role() = 'admin');
--> statement-breakpoint

-- plugins: public read, admin write
ALTER TABLE "plugins" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "plugins_select" ON "plugins" FOR SELECT USING (true);
--> statement-breakpoint
CREATE POLICY "plugins_admin_insert" ON "plugins" FOR INSERT WITH CHECK (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "plugins_admin_update" ON "plugins" FOR UPDATE USING (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "plugins_admin_delete" ON "plugins" FOR DELETE USING (public.current_user_role() = 'admin');
--> statement-breakpoint

-- skills: public read, admin write
ALTER TABLE "skills" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "skills_select" ON "skills" FOR SELECT USING (true);
--> statement-breakpoint
CREATE POLICY "skills_admin_insert" ON "skills" FOR INSERT WITH CHECK (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "skills_admin_update" ON "skills" FOR UPDATE USING (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "skills_admin_delete" ON "skills" FOR DELETE USING (public.current_user_role() = 'admin');
--> statement-breakpoint

-- users: own row read/update, admin full access
ALTER TABLE "users" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "users_select_own" ON "users" FOR SELECT USING (auth_id = auth.uid());
--> statement-breakpoint
CREATE POLICY "users_update_own" ON "users" FOR UPDATE USING (auth_id = auth.uid());
--> statement-breakpoint
CREATE POLICY "users_admin_all" ON "users" FOR ALL USING (public.current_user_role() = 'admin');
--> statement-breakpoint

-- votes: own votes only
ALTER TABLE "votes" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "votes_select_own" ON "votes" FOR SELECT USING (user_id = public.current_user_id());
--> statement-breakpoint
CREATE POLICY "votes_insert_own" ON "votes" FOR INSERT WITH CHECK (user_id = public.current_user_id());
--> statement-breakpoint
CREATE POLICY "votes_update_own" ON "votes" FOR UPDATE USING (user_id = public.current_user_id());
--> statement-breakpoint
CREATE POLICY "votes_delete_own" ON "votes" FOR DELETE USING (user_id = public.current_user_id());
--> statement-breakpoint

-- comments: public read, own write/update/delete
ALTER TABLE "comments" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "comments_select" ON "comments" FOR SELECT USING (true);
--> statement-breakpoint
CREATE POLICY "comments_insert_own" ON "comments" FOR INSERT WITH CHECK (user_id = public.current_user_id());
--> statement-breakpoint
CREATE POLICY "comments_update_own" ON "comments" FOR UPDATE USING (user_id = public.current_user_id());
--> statement-breakpoint
CREATE POLICY "comments_delete_own" ON "comments" FOR DELETE USING (user_id = public.current_user_id());
--> statement-breakpoint

-- install_events: anyone can insert (telemetry), admin read
ALTER TABLE "install_events" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "install_events_insert" ON "install_events" FOR INSERT WITH CHECK (true);
--> statement-breakpoint
CREATE POLICY "install_events_select_admin" ON "install_events" FOR SELECT USING (public.current_user_role() = 'admin');
--> statement-breakpoint

-- allowed_domains: public read (needed at signup), admin write
ALTER TABLE "allowed_domains" ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY "allowed_domains_select" ON "allowed_domains" FOR SELECT USING (true);
--> statement-breakpoint
CREATE POLICY "allowed_domains_admin_insert" ON "allowed_domains" FOR INSERT WITH CHECK (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "allowed_domains_admin_update" ON "allowed_domains" FOR UPDATE USING (public.current_user_role() = 'admin');
--> statement-breakpoint
CREATE POLICY "allowed_domains_admin_delete" ON "allowed_domains" FOR DELETE USING (public.current_user_role() = 'admin');
