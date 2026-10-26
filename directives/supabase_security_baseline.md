# Directive: the security baseline of this AIOS store

**Goal:** the store starts closed and passes `python3 execution/security_check.py` (`GATE PASSED`) before anything reads from it.
**Why it matters:** the store holds mail, calendar and customer data about real people. Treat it as personal data under the GDPR from day one, even when only one person uses it.

## Inputs
- A Supabase project in an EU region (the region is fixed at creation: check it first).
- This folder's `.env` with the keys listed in `.env.example`.

## Steps
1. **Schema through migrations only.** `python3 execution/apply_migrations.py`. Migration `0001_owner_and_privileges` closes everything first:
   - reads need an owner listed in `private.owners`, checked by `private.is_owner()`
   - the API roles `anon` and `authenticated` can only SELECT; writers use the secret key
   - a new table starts with RLS on and no grants
2. **Every later migration grants on purpose.** A new table needs `grant select on public.<t> to authenticated;` plus an owner policy. A new function needs `grant execute ... to authenticated;`. A table nobody can read is the safe failure; never fix it by opening it to everyone.
3. **Dashboard settings** (the access token cannot change these, on purpose):
   - Authentication > Sign In / Providers: sign-ups OFF, anonymous sign-ins OFF.
   - Authentication > Policies / Passwords: minimum length 12, "secure password change" ON.
   - Authentication > Users > Add user: the owner, with a strong password. Then `python3 execution/add_owner.py <their e-mail>`.
   - Project Settings > API Keys: use the `sb_publishable_` and `sb_secret_` keys. Disable the legacy JWT-based keys.
   - Project Settings > JWT Keys: revoke the legacy HS256 secret once nothing uses a legacy key.
   - Database > Settings > SSL: enforce SSL.
4. **Network allowlist.** `python3 execution/allow_my_ip.py` (needs the Supabase CLI and `SUPABASE_NETWORK_TOKEN`), or set it in Database > Settings > Network restrictions. This limits direct Postgres connections only; the API, the app and n8n are not affected.
5. **Backup.** `python3 execution/backup_db.py`, then `python3 execution/backup_db.py --restore-test`. A backup counts only after its restore test passes (it leaves `RESTORE_TEST_PASSED` in the backup folder; the gate looks for it). Backups land outside this folder on purpose, in `~/.local/share/aios-backups/<project ref>/`: they hold personal data, so they are not synced and not in git. Deleting that folder deletes every backup of this store.
6. **Gate.** `python3 execution/security_check.py` must print `GATE PASSED`. Run it after every migration and before anyone else gets access.

## Edge cases
- **RLS "on" is not protection by itself.** A policy `using (true)` with open sign-ups lets any stranger read everything. The break test (`data/tests/rls_break_test.sql`) proves the store is closed: a signed-in stranger must read 0 rows.
- **Never revoke EXECUTE on `private.is_owner()` from `authenticated`.** A policy runs its helper as the querying role; the owner would get "permission denied".
- **`sb_secret_` keys go in the `apikey` header only**, never in `Authorization`.
- **A 403 from the Management API names the missing permission.** Do not widen the stored token. Do the setting in the dashboard, or create a separate token with only that permission.
- **Free plan:** no Supabase-side backups, and the project pauses after about 7 days without activity (the symptom is "failed to fetch", not a bad key). Restore it from the dashboard.
- **A printed secret is a leaked secret:** rotate it in the dashboard, then update `.env`.

## Change log
- Shipped with the shared AIOS: an update replaces this file. Lessons about it go in `tasks/lessons.md`.
