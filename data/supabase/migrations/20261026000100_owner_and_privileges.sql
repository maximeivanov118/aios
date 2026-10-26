-- 0001 — Closed by default. Runs before any table exists, so every later table starts with no access.
-- Pattern: directives/supabase_security_baseline.md. Proof: data/tests/rls_break_test.sql (run by security_check.py).
--   * reads need an owner listed in private.owners (checked by private.is_owner())
--   * the API roles anon and authenticated never write; writers use the secret key (service_role)
--   * a new table gets RLS on automatically and no grants: each migration grants on purpose

-- 1. Owner allow-list, in a schema the Data API does not expose.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;          -- needed to evaluate the policy helper, nothing else

create table private.owners (
  user_id  uuid primary key references auth.users (id) on delete cascade,
  added_at timestamptz not null default now(),
  note     text
);
alter table private.owners enable row level security;    -- no policies: only the definer function and service_role read it
revoke all on private.owners from public, anon, authenticated;

-- True when the caller's JWT belongs to a listed owner. Empty table = nobody reads through the Data API (fails closed).
create function private.is_owner()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from private.owners o where o.user_id = (select auth.uid()));
$$;
revoke all on function private.is_owner() from public, anon;
grant execute on function private.is_owner() to authenticated;   -- a policy calls its helper as the querying role

-- 2. RLS switched on for every new public table. Recent Supabase projects ship public.rls_auto_enable() with an
--    event trigger; older ones do not, so create the same thing only when it is missing.
do $do$
begin
  if not exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                 where n.nspname = 'public' and p.proname = 'rls_auto_enable') then
    execute $fn$
      create function public.rls_auto_enable() returns event_trigger
      language plpgsql security definer set search_path = pg_catalog as $body$
      declare cmd record; tbl name;
      begin
        for cmd in select * from pg_event_trigger_ddl_commands()
                   where command_tag in ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
                     and object_type in ('table', 'partitioned table') loop
          if cmd.schema_name = 'public' then
            select c.relname into tbl from pg_catalog.pg_class c where c.oid = cmd.objid;
            execute format('alter table if exists %I.%I enable row level security', cmd.schema_name, tbl);
          end if;
        end loop;
      end $body$ $fn$;
    execute 'create event trigger ensure_rls on ddl_command_end '
            'when tag in (''CREATE TABLE'', ''CREATE TABLE AS'', ''SELECT INTO'') execute function public.rls_auto_enable()';
  end if;
end $do$;
revoke execute on function public.rls_auto_enable() from public, anon, authenticated;   -- event triggers fire without EXECUTE

-- 3. New objects start closed. Every later migration grants what it needs:
--    `grant select on public.<table> to authenticated;` and `grant execute on function public.<fn>(...) to authenticated;`
alter default privileges for role postgres in schema public revoke all on tables    from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke execute on functions from public, anon, authenticated;
-- Postgres grants EXECUTE on every new function to PUBLIC through a GLOBAL default; a per-schema revoke cannot remove a
-- global grant, so revoke it globally as well. Each migration grants EXECUTE to the role that needs it.
alter default privileges for role postgres revoke execute on functions from public;
