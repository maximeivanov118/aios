-- RLS break test for this AIOS store. Runs as postgres through the Management API:
--   python3 execution/db_query.py data/tests/rls_break_test.sql      (security_check.py runs it too)
-- Everything happens inside one DO block that ends with RAISE EXCEPTION, so Postgres rolls ALL of it back
-- (the fake auth users, the owner row, the probe table). The result travels in the exception message.
-- Pass = a signed-in stranger reads 0 rows everywhere, the owner reads every row, nobody but the service role
--        writes, anon can neither read nor call the search functions, and a new table starts with RLS on and no grants.
-- The table list is every table in public at run time, so a table added by a later migration is tested too.
-- Probe rows go into the kit tables first (rolled back with everything else), so an open policy shows up even on an
-- empty store. For tables the kit does not know, the structural checks catch it: every SELECT policy that the API
-- roles can use must call private.is_owner(), and anon must hold no privilege on any table or function.
do $$
declare
  r jsonb := '{}';
  owner_id    uuid := gen_random_uuid();
  stranger_id uuid := gen_random_uuid();
  t text;
  n bigint;
  tables text[] := array(select tablename::text from pg_tables where schemaname = 'public' order by 1);
begin
  insert into public.sources (id, kind) values ('zz_breaktest', 'mail');
  insert into public.items (source_id, external_id, kind, occurred_at, title)
  values ('zz_breaktest', 'zz_breaktest', 'mail', now(), 'breaktest probe');
  insert into public.documents (folder, rel_path, project, kind, content, size_bytes, content_sha)
  values ('zz_breaktest', 'probe.md', 'zz_breaktest', 'md', 'breaktest probe', 15, 'x');

  r := r || jsonb_build_object('open_policies', coalesce((
    select jsonb_agg(p.tablename || '.' || p.policyname) from pg_policies p
    where p.schemaname = 'public' and p.cmd in ('SELECT', 'ALL')
      and p.roles && array['public', 'anon', 'authenticated']::name[]
      and coalesce(p.qual, '') not like '%is_owner()%'), '[]'::jsonb));
  r := r || jsonb_build_object('anon_table_grants', coalesce((
    select jsonb_agg(distinct table_name) from information_schema.role_table_grants
    where table_schema = 'public' and grantee in ('anon', 'PUBLIC')), '[]'::jsonb));
  r := r || jsonb_build_object('anon_functions', coalesce((
    select jsonb_agg(p.proname) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.prokind = 'f' and has_function_privilege('anon', p.oid, 'execute')), '[]'::jsonb));

  foreach t in array tables loop                                   -- ground truth, as postgres
    execute format('select count(*) from public.%I', t) into n;
    r := r || jsonb_build_object('real_' || t, n);
  end loop;

  insert into auth.users (id, aud, role, email)
  values (owner_id, 'authenticated', 'authenticated', 'owner@breaktest.invalid'),
         (stranger_id, 'authenticated', 'authenticated', 'stranger@breaktest.invalid');
  insert into private.owners (user_id, note) values (owner_id, 'break test');

  -- 1. A signed-in stranger (a real account, not an owner).
  perform set_config('request.jwt.claims', json_build_object('sub', stranger_id, 'role', 'authenticated')::text, true);
  set local role authenticated;
  foreach t in array tables loop
    begin
      execute format('select count(*) from public.%I', t) into n;
      r := r || jsonb_build_object('stranger_' || t, n);
    exception when insufficient_privilege then
      r := r || jsonb_build_object('stranger_' || t, 0);           -- no grant at all is also "reads nothing"
    end;
  end loop;
  reset role;

  -- 2. The owner: must read everything (positive control), must not write.
  perform set_config('request.jwt.claims', json_build_object('sub', owner_id, 'role', 'authenticated')::text, true);
  set local role authenticated;
  foreach t in array tables loop
    begin
      execute format('select count(*) from public.%I', t) into n;
      r := r || jsonb_build_object('owner_' || t, n);
    exception when insufficient_privilege then
      r := r || jsonb_build_object('owner_' || t, 'refused');
    end;
  end loop;
  begin
    insert into public.documents (folder, rel_path, project, kind, content, size_bytes, content_sha)
    values ('BREAKTEST', 'x', 'x', 'md', 'x', 1, 'x');
    r := r || '{"owner_insert": "ALLOWED"}';
  exception when insufficient_privilege then
    r := r || '{"owner_insert": "refused"}';
  end;
  reset role;

  -- 3. The publishable (anon) key.
  perform set_config('request.jwt.claims', '{"role": "anon"}', true);
  set local role anon;
  begin
    select count(*) into n from public.items;
    r := r || jsonb_build_object('anon_items', n);
  exception when insufficient_privilege then
    r := r || '{"anon_items": "refused"}';
  end;
  begin
    insert into public.documents (folder, rel_path, project, kind, content, size_bytes, content_sha)
    values ('BREAKTEST', 'y', 'x', 'md', 'x', 1, 'x');
    r := r || '{"anon_insert": "ALLOWED"}';
  exception when insufficient_privilege then
    r := r || '{"anon_insert": "refused"}';
  end;
  begin
    perform * from public.search_documents('test');
    r := r || '{"anon_search": "ALLOWED"}';
  exception when insufficient_privilege then
    r := r || '{"anon_search": "refused"}';
  end;
  reset role;

  -- 4. A table and a function created by a future migration: RLS on, no grants, no EXECUTE for the API roles.
  create table public.zz_breaktest_probe (id int primary key);
  create function public.zz_breaktest_fn() returns int language sql as 'select 1';
  r := r || jsonb_build_object(
    'new_table_rls', (select relrowsecurity from pg_class where oid = 'public.zz_breaktest_probe'::regclass),
    'new_table_anon_select', has_table_privilege('anon', 'public.zz_breaktest_probe', 'select'),
    'new_table_auth_select', has_table_privilege('authenticated', 'public.zz_breaktest_probe', 'select'),
    'new_fn_anon_exec', has_function_privilege('anon', 'public.zz_breaktest_fn()', 'execute'),
    'new_fn_auth_exec', has_function_privilege('authenticated', 'public.zz_breaktest_fn()', 'execute'));

  raise exception 'BREAKTEST %', r;
end $$;
