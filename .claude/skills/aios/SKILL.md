---
name: aios
description: 'Guides a company owner through building their AI operating system (AIOS) one stage at a time: folder, context, a private Supabase store, company knowledge in it, connected tools, two weeks of use by hand, then the first own skill. Says the one next step, proven by checks. Use when the owner says "what is my next step", "update the AIOS", "where am I with the AIOS", "continue the AIOS", "set up an AIOS for a company", or invokes /aios. Not for loading one folder into the store (use knowledge-ingest) or the session brief (use prime).'
---

# /aios — build the AIOS, one stage at a time

An AIOS is a layer around a business: it knows the company (context), keeps its data in one private store, reads its tools, and runs skills, agents and apps on top. It is built in layers, not leaps. This skill is the guide: it always knows where the owner is and says the next step.

The scripts live in this skill's base directory (shown when the skill loads), called `<skill dir>` below.

## Step 1 — Where are we? (every time, before anything else)
- `python3 "<skill dir>/scripts/aios_status.py"` from the AIOS folder (or `--root <folder>`).
- "no aios.json": no AIOS yet. Open `references/stage-0-start.md` and start there.
- Otherwise: show the stage table, then say the **one** next step in one or two plain sentences. Ask nothing else yet.

## Step 2 — Work the next stage
Open the reference for that stage, and only that one:

| Stage | Reference | Who does the work |
|---|---|---|
| 0 Start | `references/stage-0-start.md` | Claude, two answers from the owner |
| 1 Context | `references/stage-1-context.md` | owner talks, Claude writes |
| 2 Data store | `references/stage-2-data.md` | owner in the Supabase dashboard, Claude runs the scripts |
| 3 Knowledge | `references/stage-3-knowledge.md` | owner gathers, Claude converts and loads (`/knowledge-ingest`) |
| 4 Connect tools | `references/stage-4-connect.md` | owner signs in, Claude configures and tests |
| 5 Use it by hand | `references/stage-5-manual.md` | owner works for 1 to 2 weeks, Claude logs |
| 6 First own skill | `references/stage-6-tools.md` | owner + Claude, one sitting |

Walk the stage **one step at a time**: say the step, wait until it is done, check it, then the next step. After the stage's last step, run the status again and show what moved.

## Step 3 — Record only what a check proved
`aios_status.py record <stage> ...` writes progress into `aios.json`, and it refuses when the check fails. Never edit `aios.json` by hand. Stages 0 and 1 have no record step: their checks read the files directly.
Stages 0 to 3 and the store read of stage 4 are **proven** by scripts. The work-tool connections of stage 4, and stages 5 and 6, are **attested**: no script can see a claude.ai connector, two weeks of work or a skill doing a real task. For those, record only what really happened, in the owner's words, and say "attested" when you report them.

## Updates (a folder that holds `aios-source.json`)
The shared AIOS (every file git tracks) is the same for every company; the company's own part (everything git ignores) is never shared.
- Once per session, after Step 1: `python3 "<skill dir>/scripts/aios_update.py" --check`. If an update waits, say so in one line. Do not update unasked.
- When the owner says "update": `python3 "<skill dir>/scripts/aios_update.py"`. Show its report: what changed, what it set aside in `.tmp/` (a local edit to a shared file, or an own file in the way), and any new migration to apply with the stage 2 rules.
- Never edit a shared file to fix something for this company: put the change in its own part (a project, an own skill, `tasks/lessons.md`).

## Rules
- **Keys never enter the chat.** The owner types them into `.env` in an editor. Never read `.env`, never print it, never ask for a value. A key pasted into the chat by mistake is leaked: tell the owner to rotate it now.
- **Layers, not leaps.** If the owner wants to jump ahead, say once why the earlier layer matters, then do what they decide. The status table keeps showing the gap.
- **The kit ends at stage 6.** A scheduled tool or a dashboard is not part of it: when the owner wants one, start it as its own project with `/setup`, one tool at a time. Claude does not send anything.
- **Plain words.** The owner may not be technical. Short sentences. Explain a term once, the first time (store, migration, MCP, skill).
- **Never invent.** A fact, a number or a result that was not given or measured stays blank, with a note.
- **Log real work.** In stage 5 and after, every real task done with Claude gets a row in `tasks/repeats.md` at its end.
- End every session with the status in brief form: `aios_status.py --brief`.
