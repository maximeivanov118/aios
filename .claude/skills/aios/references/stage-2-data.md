# Stage 2 — Data store (Supabase)

**Goal:** one private Supabase project for this company, with the AIOS schema, closed to strangers, backed up.
**Who:** the owner clicks in the Supabase dashboard and types keys into `.env`; Claude runs the scripts and checks.
**Plan one quiet sitting:** about ten dashboard steps come before any payoff. Walk them one at a time.
**Done when:** `aios_status.py record data` passes: every migration applied and `security_check.py` prints `GATE PASSED`.
Full rules: `directives/supabase_security_baseline.md` in the AIOS folder.

## Steps (one at a time; check each before the next)
1. **Account and project.** supabase.com → sign up (the company's e-mail, not a personal one). New project: name `<Company> AIOS`, region in the EU (for example Frankfurt), a strong database password kept in a password manager (the AIOS does not need it). The free plan is fine to start; it pauses after about a week with no activity, and a paused project is restored from the dashboard.
2. **`.env`.** `cp .env.example .env`. The owner opens `.env` in a text editor and fills each line; the comments say where each value is in the dashboard. Claude never reads `.env` and never asks for a value: it runs `aios_status.py`, which checks the key NAMES only.
3. **Access token.** supabase.com/dashboard/account/tokens → new token, for this project only: everything Read, plus Database and Migrations Read-write. Into `.env` as `SUPABASE_ACCESS_TOKEN`.
4. **Schema.** `python3 execution/apply_migrations.py` → three migrations APPLIED. Run it again: "nothing to apply".
5. **Dashboard settings** (step 3 of the directive): sign-ups off, anonymous sign-ins off, password minimum 12, secure password change on, legacy JWT keys disabled, legacy HS256 key revoked, SSL enforced. Walk them one by one; the owner says "done" after each.
6. **Owner account.** Authentication > Users > Add user (the owner's e-mail, 12+ character password). Then `python3 execution/add_owner.py <that e-mail>`.
7. **Network allowlist.** Database > Settings > Network restrictions: only the owner's current IP (or `python3 execution/allow_my_ip.py` when the Supabase CLI is installed).
8. **Backup.** `python3 execution/backup_db.py` then `python3 execution/backup_db.py --restore-test` → RESTORE TEST PASSED. Only a restore-tested backup counts for the gate. Tell the owner where backups live: outside the AIOS folder, in `~/.local/share/aios-backups/<project ref>/` (not synced, not in git, the newest 14 kept). Deleting that folder deletes them.
9. **Gate.** `python3 execution/security_check.py`. Each FAIL line names the control; fix it in the dashboard and run again.
10. **Record.** `python3 "<skill dir>/scripts/aios_status.py" record data` (it runs the checks itself).

## Common problems
- `http=401` / `403` from a script: the token is wrong or lacks a permission. The 403 text names the permission. Make a new token with it; never widen the existing one beyond what the step needs.
- `Failed to fetch` / `curl exit 6` / nothing answers: the project is paused (free plan). Restore it in the dashboard and wait about 4 minutes.
- A key was pasted into the chat by mistake: it is leaked. Rotate it in the dashboard now, then update `.env`.
- "GATE FAILED: backup": run step 8, both commands; the gate wants a restore-tested backup younger than 8 days.
- "GATE FAILED: RLS break test" with `open policies=[...]` or `anon grants=[...]`: a migration opened a table. Write a new migration that drops that policy or grant; never edit the applied one.
