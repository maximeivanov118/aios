---
name: setup
description: 'Scaffolds a new project folder inside the AIOS with the directive / execution layout: a CLAUDE.md pointing to the AIOS rules, directives/, execution/, active/plans/, .tmp/, its own skills and agents folders, and a .env holding only the keys the owner approves. Use when the owner says "set up a new project", "start a folder for this job", "scaffold a project", or invokes /setup. Not for starting the AIOS itself (use aios) or for loading documents (use knowledge-ingest).'
---

# /setup — a new project inside the AIOS

A project is one job with its own instructions and tools (for example `projects/invoice-chaser/`). It lives inside the AIOS so it inherits the AIOS rules and `context/`.

## Step 1 — Where
- Find the AIOS root (the folder above with `aios.json`). The project goes in `<root>/projects/<kebab-name>/`, unless the owner names another folder inside the AIOS.
- Never outside the AIOS root, never over an existing folder's files.

## Step 2 — Three questions, in one message
1. What is this project for? (one sentence)
2. Which tools or services will it use? ("not sure yet" is fine)
3. Which keys may this project's `.env` hold? List the key NAMES in the AIOS `.env` (names only: `grep -oE '^[A-Z0-9_]+' "<root>/.env"`), the owner picks, or "none".

## Step 3 — Create (skip anything that exists)
```
projects/<name>/
├── CLAUDE.md                ← from the block below
├── .env                     ← header + the approved keys only
├── .claude/settings.json    ← deny reading other .env files
├── .claude/skills/  .claude/agents/
├── directives/  execution/  active/plans/  .tmp/      (each with a .gitkeep)
```

`CLAUDE.md`:
```markdown
# CLAUDE.md — <name>

> Status: active · since <YYYY-MM-DD> · <one-line purpose>

<one sentence from question 1>

Tools: <answer 2, or TBD>.
Company facts: the AIOS `context/` (two folders up). AIOS rules: the AIOS `CLAUDE.md`. Both win over anything here.

- Directives (`directives/`) say what to do. Scripts (`execution/`) do it. Claude reads the directive and runs the scripts.
- Keys: only this folder's `.env`. Never print it.
- Output → `active/`, scratch → `.tmp/`, plans → `active/plans/<date>-<name>.md`.
- When a script breaks: fix it, test it, then write what you learned into its directive.
```

`.env`: write the header line `# <name> — project keys. Only this project reads this file.` Then copy each approved key file-to-file, so the value never enters the chat:
`grep '^KEY_NAME=' "<root>/.env" >> "<project>/.env"`. Check by names only: `grep -oE '^[A-Z0-9_]+' "<project>/.env"`.

`.claude/settings.json`:
```json
{ "permissions": { "deny": ["Read(./.env)", "Read(../../.env)"] } }
```

## Step 4 — Confirm
List what was created, and the next step: "write the first directive in `directives/`".
