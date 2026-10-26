# Stage 0 — Start

**Goal:** a folder that is an AIOS: rules (`CLAUDE.md`), the state file (`aios.json`), the empty parts.
**Who:** the owner answers two questions; Claude runs one script.
**Done when:** `aios_status.py` shows stage 0 done (CLAUDE.md exists, `.gitignore` holds `.env`).

## Before anything, check the machine (say what is missing, do not install silently)
- `python3 --version` → 3.9 or newer. Missing: python.org installer (macOS / Windows) or the system package.
- `curl --version` → present on macOS, Linux and Windows 10+.
- Claude Code is signed in with a paid Claude plan (Pro or Max). The AIOS runs on that plan; nothing in this kit needs API credits.
- The folder: a normal local folder is best, for example `~/<Company> AIOS`. A synced folder (iCloud, Dropbox, OneDrive) works for documents but can create "conflicted copy" files; if the owner wants a sync for safety, git (below) is the better backup.

## Steps
1. Ask, in one message: the company name, and the owner's full name.
2. Run, from the folder that becomes the AIOS:
   `python3 "<skill dir>/scripts/aios_init.py" --company "<Company>" --owner "<Name>"`
   It copies the template, never overwrites a file, and copies the companion skills (`/setup`, `/knowledge-ingest`, `/prime`, and the shared ones) into `.claude/skills/`.
3. Run `python3 "<skill dir>/scripts/aios_status.py"` and show the table.
4. Recommend (optional: it gives the folder a history and a copy off this computer): a **private** GitHub repository for this folder. `git init`, then the first commit only after checking `git status` shows no `.env`. Never push before that check.
5. Tell the owner, in two sentences, what the next stage is (Context) and how long it takes (one sitting of 30 to 60 minutes).

## Common problems
- "already an AIOS": the folder has `aios.json`. Run the status instead.
- The owner opened Claude Code in the wrong folder: stop, ask them to open the AIOS folder itself, so `CLAUDE.md` loads every session.
