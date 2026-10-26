# Stage 3 — Knowledge into the store

**Goal:** the company's own knowledge (offers, SOPs, FAQ, customer types, brand voice) is in the store and Claude finds it by search.
**Who:** the owner gathers the documents; Claude converts, checks and loads them.
**Done when:** `aios_status.py record knowledge --query "<phrase>"` passes: documents in the store, and a search for a phrase from one of them finds it.
Tool and rules: `/knowledge-ingest` and `directives/knowledge_ingest.md`.

## Steps
1. **List what exists.** Ask: where do the price list, the proposals that won, the how-we-do-it notes, the FAQ and the brand guide live today (Drive, Notion, Word files, a website, nowhere)? Write the list in the chat.
2. **Gather into `knowledge/<topic>/`** (topics in `knowledge/README.md`). Copy files; never move the owner's originals.
3. **Convert:** Word / PowerPoint → `python3 execution/convert_docs.py <file or folder> --out knowledge/<topic>` (copy the originals into `.tmp/import/` first). PDF → read it and write Markdown with a clear `# Title`. Website pages → read the page, keep the text that is true, drop menus and footers.
4. **Write what is missing.** The most useful documents are often in the owner's head: "how do you handle a refund?", "what do you say when a lead says it is too expensive?". Interview, write one file per answer in `knowledge/faq/` or `knowledge/sops/`, read it back.
5. **Clean:** no passwords, bank details, health data, or personal data the company has no right to keep. The ingest tool also refuses any file whose text looks like a key or a password, and names it: remove that line, then load again.
6. **Load** each topic with `/knowledge-ingest knowledge/<topic>` (dry run first, the owner's yes, then the run; it verifies every row).
7. **Prove:** pick a phrase from one file, `python3 execution/search_store.py "<phrase>"` → that file on top.
8. **Record:** `python3 "<skill dir>/scripts/aios_status.py" record knowledge --query "<phrase>"`.

## Keeping it fresh
A file changed → run the same `/knowledge-ingest` again (only changes are sent). Once a month at `/prime`: "anything new to add to knowledge?"

## Common problems
- Search finds nothing: the phrase is not literally in the text (search is full-text, not "meaning"). Try words that really appear, or give the file a better `# Title`.
- Huge exports (a whole Drive): stop. Pick the 20 documents that matter most. More is not better; findable is better.
