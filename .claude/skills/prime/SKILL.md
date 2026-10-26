---
name: prime
description: 'Starts a work session in the AIOS with a short brief: the company and its current goal from context/, where the AIOS build stands and its next step, what is stale, and the last tasks logged. Use when a session starts, or when the owner says "prime", "brief me", "where were we", "what is going on", or invokes /prime. Not for working through a build stage (use aios).'
---

# /prime — the session brief

Run from the AIOS root (the folder with `aios.json`). Keep the brief under 15 lines.

## Steps
1. **Build state:** `python3 .claude/skills/aios/scripts/aios_status.py --brief`.
2. **Context:** read `context/strategy.md` (goal, priorities) and `context/current-data.md` (numbers, open problems). Read `business-info.md` and `personal-info.md` only if this session needs them.
3. **Staleness:** a context file whose "Updated:" date is older than 30 days, or `current-data.md` older than 7 days → say which, and offer to update it.
4. **Recent work:** the last 3 rows of `tasks/repeats.md`, and any task logged 3+ times that is not a skill yet ("ready to become a skill").
5. **Output**, in this order:
   - one line: company, goal, North Star number with its date
   - one line: AIOS stages done and the next step
   - stale items, if any
   - recent work and skill candidates, if any
   - "What do you want to do?"

## Rules
- Facts come from the files, never from memory. A missing number is shown as missing.
- Never read `.env`.
