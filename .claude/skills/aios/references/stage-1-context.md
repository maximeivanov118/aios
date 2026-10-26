# Stage 1 — Context

**Goal:** the four `context/` files describe the company well enough that a new employee (or Claude) could act like the owner would.
**Who:** the owner talks; Claude asks, writes, and reads back.
**Done when:** each file has no `<!-- FILL` marker left and 60+ words of real content (`aios_status.py` checks it).

## The five ways in (offer them; most owners mix two or three)
1. **Interview** — Claude asks, one question at a time, the owner answers by voice or text.
2. **Drop folder** — the owner puts existing material in `.tmp/import/` (website text, pitch deck, about-us, old business plan, price list). Claude reads it and drafts.
3. **Paste** — the owner pastes text into the chat (never keys).
4. **URL** — the company website: Claude reads the public pages and drafts.
5. **Memory export** — the owner exports what another AI assistant knows about them (e.g. "tell me everything you know about me and my business") and pastes it.

## How to run the interview
- One file at a time, in this order: business-info, personal-info, strategy, current-data.
- One question at a time. Each `<!-- FILL: ... -->` comment is the question to ask for that section.
- Write in the owner's words, shortened. Never invent a fact, a number or a name. Unknown → leave the line out and say so.
- After each section: read it back in 2 or 3 lines, ask "right?", then replace the FILL comment with the text.
- Numbers (current-data) need a date and a source. "About 40 customers, owner's estimate, {{date}}" is fine. A guessed number is not.
- Drafts from the drop folder or the website are shown to the owner before they replace a FILL comment.

## After the four files
- Run the status. Show what moved.
- Tell the owner: these files are the single source of truth. When something changes (new price, new hire, new goal), they say "update the context" and Claude edits the file.

## Common problems
- The owner wants to skip to the tools: say why not, once. Tools built without context make generic output; the context is what makes the AIOS theirs. Then continue with the shortest file (personal-info).
- Personal data about other people (staff, customers): keep to roles and names the owner is fine with; no health, family or salary details.
