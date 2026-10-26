# Start here — your AIOS

This folder becomes your company's AI operating system (AIOS): Claude that knows your business, reads your documents and tools, and takes repeated work off your plate. You build it in seven short stages. Claude tells you the next step every time.

> **Early version.** The database setup (stage 2) was tested on a local copy of the database, and its parts against a real Supabase project. It has not yet been run start to finish on a brand-new project. If a step fails, the message names the check that failed: fix that one thing and run it again.

## What you need
- **A Mac or a Linux computer.** Windows has not been tested yet.
- **Claude Code**, signed in with a paid Claude plan (Pro or Max): https://claude.com/claude-code
- **Python 3.9 or newer** (`python3 --version` in a terminal).
- **A free Supabase account** (stage 2): https://supabase.com
- About an hour for the first sitting (stages 0 and 1), then a few short sittings.

## How to start
1. Get the folder, one of two ways:
   - **With updates (recommended):** in a terminal, `git clone https://github.com/maximeivanov118/aios "Your company AIOS"` (use your company's name).
   - **From the zip:** unzip it and rename the `aios-kit` folder to `<Your company> AIOS`. Your first "update the AIOS" links it to the repository (git is needed then).
2. Keep the folder somewhere normal on your computer (for example your home folder) and open it in Claude Code (in a terminal: `cd` into it, then `claude`; or open it in VS Code with the Claude extension).
3. Type **`/aios`** and press Enter. Claude asks two questions and sets everything up.
4. Any time later: `/prime` at the start of a session, `/aios` to continue the build, "update the AIOS" for the newest version.

## What is shared and what is yours
Every file that came with this folder is the **shared AIOS**: the same for every company, kept up to date by "update the AIOS". Everything you and Claude add (your company context, documents, task logs, projects, own skills, keys) is **yours**: `.gitignore` keeps all of it out of git, so it is never shared and an update never touches it.

## The stages
0 Start · 1 Context (who you are) · 2 Data store (your private database) · 3 Knowledge (your documents in it) · 4 Connect tools (mail, calendar, files) · 5 Use it by hand for two weeks · 6 Your first own skill.
After stage 6 the AIOS grows the same way: the next task you repeat becomes the next skill, and a bigger tool becomes a project of its own (`/setup`).

## Three rules that keep it safe
- **Never paste a password or key into the chat.** You type keys into the `.env` file yourself; Claude only checks that they are there.
- **Nothing is sent without you.** Mail and messages are drafts until you send them.
- **Nothing goes into the database without your yes**, one folder at a time.

## Skills included
`/aios` (the guide), `/prime` (session brief), `/knowledge-ingest` (documents into the store), `/setup` (a new project folder), plus the shared skills listed in `SHARED-SKILLS.md`.
