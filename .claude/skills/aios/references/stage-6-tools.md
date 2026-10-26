# Stage 6 — Your first own skill

**Goal:** the task the owner repeats most becomes a skill: one command that does it their way, every time.
**Who:** the owner and Claude, one sitting.
**Done when:** one own skill exists in `.claude/skills/`, it has done one real task, and that is recorded.

## Step 1 — The first own skill (owner + Claude, one sitting)
- Take the task with the most rows in `tasks/repeats.md`.
- Run `/skill-creator`. Feed it the log rows for that task (what went wrong is what the skill must handle) and the matching `context/` and `knowledge/` files.
- One mission per skill, one sentence, no "and". A task that needs an "and" is two skills.
- Test it on the next real occurrence of the task. Log it in `repeats.md` as usual.
- When it has done one real task well: `aios_status.py record tools --evidence "<the skill, the task it did, and when>"`.

## Step 2 — Decide what is a skill, an agent, or a tool
| It is... | when... |
|---|---|
| a **directive + script** | the steps are always the same (a report, a data pull). The script does the work, the directive says how. |
| a **skill** | the owner starts it and judgment is needed each time (a proposal, a reply). |
| an **agent** (`.claude/agents/`) | it reads a lot (keep it out of the main session), a cheaper model is enough, it needs fewer permissions, or it runs many times in parallel. |
| a **scheduled tool** (cadence) | it must run without anyone asking: a morning brief, a mail collector, a weekly report. Not part of this kit: start it as its own project with `/setup` (for example n8n for the trigger, a scheduled routine for the Claude step). |

## After stage 6
The AIOS is complete, and it grows the way it started: the next repeat in `tasks/repeats.md` becomes the next skill. A heavier tool (a mail collector, a weekly report, a dashboard) is a project of its own: `/setup` makes its folder inside the AIOS, and its first directive says what it must do. Measured results (hours saved per week, errors) go in `context/current-data.md`.

## Common problems
- The owner wants an agent for everything: most repeats need only a skill or a directive. An agent is for one of the four reasons above.
- A tool would send, pay or delete: it drafts, and the owner approves. Always.
