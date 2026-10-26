# Stage 5 — Use it by hand

**Goal:** know which tasks are worth automating, by doing them with Claude first. Nothing gets automated that was never done by hand.
**Who:** the owner works; Claude helps with the task and logs it.
**Done when:** `tasks/task-audit.md` has 5+ tasks, `tasks/repeats.md` has 10+ log rows, and the owner records the stage (normally after one to two weeks).

## Step 1 — The task audit (one sitting, about 30 minutes)
Walk through a normal week, Monday to Friday, morning to evening. For each recurring task, one row in `tasks/task-audit.md`:
who does it, how often, minutes each time, hours per week, the tools used, automate or augment, pain 1 to 3, value = hours × pain.
- **Automate** = it can leave the owner's plate (chasing invoices, sorting mail, weekly reports).
- **Augment** = still the owner's job, done faster (proposals, hard replies, planning).
Sort by value. The top 3 are the tasks to do with Claude first.

## Step 2 — Two weeks of real use
- Each time the owner does one of these tasks with Claude, add one row to `tasks/repeats.md`: date as YYYY-MM-DD, task (same name as in the audit), minutes with Claude, minutes before (both as plain numbers), what went wrong or was missing. The stage needs 10+ such rows on 5+ different days, spread over at least a week.
- Claude adds the row itself at the end of the task and asks only for the two minute numbers.
- What went wrong is the most valuable column: missing context → update `context/`; missing document → add it to `knowledge/`; missing tool → stage 4.

## Step 3 — Spot the repeats
The third row for the same task is the signal. Say it: "This is the third time we did <task>. In stage 6 it becomes a skill." Do not build it yet: keep using, the log keeps teaching.

## Record
When the log is honest (10+ rows, the top tasks repeated): `aios_status.py record manual --evidence "<n> rows over <n> days; repeated: <tasks>"`.

## Common problems
- The owner forgets to use it: suggest one fixed slot (the first 20 minutes of the day with `/prime`).
- Every task looks worth automating: the value column decides, not enthusiasm.
