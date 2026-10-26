# Stage 4 — Connect the tools

**Goal:** in any session, Claude can read the store and at least one work tool (mail, calendar, files, CRM), read-only first.
**Who:** the owner signs in to each service; Claude configures, tests with a real read, and records.
**Done when:** `.mcp.json` holds the Supabase MCP, and `aios.json` lists at least one connection with evidence of a real read.

## Step 1 — The store, read-only
1. `python3 "<skill dir>/scripts/aios_status.py" mcp` → writes `.mcp.json` with the hosted Supabase MCP, read-only, limited to this project.
2. The owner restarts Claude Code in the AIOS folder and runs `/mcp` → Supabase → sign in in the browser.
3. Test: ask the Supabase MCP for `select count(*) from public.documents`, then record its answer: `aios_status.py record mcp --count <that number>`. The script compares it with the store; a mismatch means the MCP is not really connected.

## Step 2 — Work tools (pick from the task audit, or from the owner's day)
Take them in this order of preference; stop at the first that works for the tool:
1. **Claude connectors** (claude.ai → Settings → Connectors: Gmail, Google Calendar, Google Drive and others). Signed in once there, they show up in Claude Code sessions of the same account. No keys to handle.
2. **The vendor's official remote MCP server** (many CRMs, Notion, Slack, Stripe and others publish one). Add it to this AIOS only: `claude mcp add --transport http --scope project <name> <url>` (read the vendor's MCP page first for the URL and the sign-in). It lands in `.mcp.json`.
3. **No MCP at all:** the tool's API through a script in `execution/`, with its key in `.env`. That is a small project of its own: note it in `tasks/task-audit.md` and start it after stage 6 with `/setup`.

For each connection:
- **Read-only first.** If the service asks for scopes, pick read. Sending, deleting and paying stay off.
- **Test with a real read** the owner can check: the 3 latest mail subjects, tomorrow's first meeting, the newest file in a folder.
- **Record:** `aios_status.py record connect --name <tool> --kind <mail|calendar|drive|crm|chat|other> --how "<connector / MCP / script>" --evidence "<what was read, and when>"`.

## Later, not now: automatic collection into the store
Mail and calendar are read live through the connectors in this stage. Copying them into the store on a schedule (so the dashboard and search see them) is a collector: an n8n workflow or a scheduled routine writing to `public.sources` and `public.items` with the secret key. That is a scheduled tool, not part of this kit: start it after stage 6 as its own project with `/setup`.

## Common problems
- A connector does not show in Claude Code: the session is signed in with another account, or the connector was added after the session started. Restart.
- The MCP asks for write access: decline and look for a read-only option; if none exists, do not connect it yet: note it in `tasks/task-audit.md`.
- Personal and work accounts mixed: connect the work account only.
