# CLAUDE.md — the AIOS

> The shared AIOS rules: every company's AIOS has this same file. `/aios` says the next step; "update the AIOS" brings the newest version.

This folder is the AI operating system (AIOS) of the company named in `aios.json`. Who the company is lives in `context/`.
An AIOS is a layer around the business: it knows the company (context), holds its data in one private store, connects to its tools, and runs skills and agents on top. It is built in layers, not leaps: each part is finished before the next one starts.

## Two parts: the shared AIOS and the company's own

- **Shared:** every file that came with the AIOS repository (`git ls-files` lists them): this file, `execution/`, `directives/`, `data/`, `.claude/settings.json` and the skills listed in `.claude/skills/.kit-manifest`. Every company has the same ones, and "update the AIOS" replaces them with the newest version. Never edit them.
- **Own:** everything else: `context/`, `knowledge/`, `tasks/`, `active/`, `projects/`, own skills and agents, `.env`, `aios.json`. git ignores all of it (`.gitignore`), so it is never shared and an update never changes it. New work goes here: a new tool or job is a project (`/setup` → `projects/<name>/`), personal permissions go in `.claude/settings.local.json`.

## The five parts, and where each one lives

| Part | What it is | Where |
|---|---|---|
| 1 Context | who the company is, how it works, what it wants now | `context/` (4 files, read them before any business task) |
| 2 Data | one private Supabase store: company knowledge, mail, calendar, records | `data/` (schema), `execution/` (tools), the store itself in Supabase |
| 3 Workspace | Claude Code, this file, the connected tools (MCP) | `CLAUDE.md`, `.claude/`, `.mcp.json` |
| 4 Skills and agents | repeatable jobs as `/skills`, workers in `.claude/agents/` | `.claude/skills/`, `.claude/agents/`, `directives/` |
| 5 Apps | tools and a dashboard on top of the store | not in this kit: each one is a project of its own (`/setup`); links in `aios.json` → `apps` |

Progress lives in `aios.json`, checked by `/aios`. Never edit `aios.json` by hand: `aios_status.py record ...` writes it only after a check passes.

## Every session

1. Start with `/prime`: a short brief and the next step.
2. `context/` is the single source of truth for company facts. A fact said elsewhere that differs from `context/` is wrong. New facts or numbers → update the matching `context/` file (ask the owner first).
3. To find company knowledge, search the store (Supabase MCP, read-only), or `python3 execution/search_store.py "<words>"`.

## Rules

- **Secrets:** keys live only in this folder's `.env`. Never print, read aloud or paste a key, and never ask the owner to paste one in the chat: they type it into `.env` themselves. Scripts read `.env`; Claude does not. A guard (`.claude/hooks/env_guard.py`) refuses any tool call that would show `.env`; never work around it.
- **The store:** the schema changes only through a new file in `data/supabase/migrations/`, applied with `python3 execution/apply_migrations.py`. Never in the dashboard, never by editing an applied migration. After every migration, `python3 execution/security_check.py` must print `GATE PASSED`.
- **Nothing goes into the store by default.** A folder goes in only when the owner says "put <folder> into Supabase" (`/knowledge-ingest`). Folders listed in `aios.json` → `never_ingest` never go in.
- **Draft, don't send.** Mail, messages and posts are drafts for the owner to send. No agent sends, pays, deletes or publishes on its own.
- **Read-only first.** A new tool connection starts read-only. Write access is added on purpose, one action at a time.
- **Paid calls:** anything that spends money (API credits, paid scrapers) needs the owner's yes for that run, with the expected cost.

## Folders

```
context/      the 4 context files              knowledge/   company documents waiting to go into the store
data/         schema (migrations) + tests      execution/   deterministic Python tools
directives/   plain-language SOPs              tasks/       task audit + the log of tasks done by hand
active/       everything generated (plans/ and the output of every task)
.tmp/         scratch, safe to delete          .claude/     skills, agents, settings
```

No loose files at the root. Output goes to `active/<subfolder>/`, scratch to `.tmp/`.

## How work gets done here (directive → orchestration → execution)

- A **directive** (`directives/<job>.md`) says what to do: goal, inputs, tools, output, edge cases.
- **Claude** reads the directive, runs the tools in order, handles errors and asks when something is unclear.
- An **execution** script (`execution/<job>.py`) does the work the same way every time.
When a script breaks: read the error, fix the script, test it again, then add what was learned to its directive. A shared script or directive is the exception: never edit it (the next update sets the edit aside); write the problem and the workaround in `tasks/lessons.md`.
A job done by hand for the third time becomes a skill (`/skill-creator`). A skill that needs its own context, a cheaper model or many parallel runs becomes an agent.
