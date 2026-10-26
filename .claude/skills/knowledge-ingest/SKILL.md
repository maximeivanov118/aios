---
name: knowledge-ingest
description: 'Puts one folder of company documents into the AIOS Supabase store, or updates, checks or removes it: converts Word and PowerPoint to Markdown, dry-runs, loads only after the owner says yes, verifies every row, and proves the folder is findable by search. Use when the owner says "put this folder into Supabase", "add these documents to the AIOS", "load the knowledge", "update the store", "what is in the store", or invokes /knowledge-ingest. Not for the whole AIOS build (use aios) or for mail and calendar collection (a scheduled tool, not part of this kit).'
---

# /knowledge-ingest — one folder into the store

Directive: `directives/knowledge_ingest.md` in the AIOS folder. Tool: `execution/ingest_folder.py`. Run everything from the AIOS root (the folder with `aios.json`).

## Steps
1. **Which folder.** It must be inside the AIOS, normally `knowledge/<topic>`. Files elsewhere: copy them into `knowledge/<topic>/` first (copy, never move the owner's originals). Refuse "everything" or the AIOS root: one folder at a time.
2. **Convert.** `.docx` / `.pptx`: `python3 execution/convert_docs.py <file or folder> --out knowledge/<topic>` (`--out` is required). PDF: read it page by page and write one Markdown file per document, starting with `# <Title>`. Excel: ask the owner for a CSV export.
3. **Look for what must not go in:** passwords, bank details, health data, personal data the company may not keep. Tell the owner what you found, and leave it out.
4. **Dry run.** `python3 execution/ingest_folder.py <folder> --dry-run`. Show the count of files to write and to delete. Ask: "Load these <n> files?"
5. **Run on yes.** `python3 execution/ingest_folder.py <folder>`. Success = the last line says `missing=0 extra=0 mismatched=0` and the exit code is 0. Anything else: show the line, stop. Files it skipped (`secret-content`, `symlink`, `never-ingest`) are listed: tell the owner which and why.
6. **Prove it is findable.** Take a distinctive phrase from one file: `python3 execution/search_store.py "<phrase>"`. That file must be in the hits.
7. **First load only:** record stage 3 with the aios skill's status script: `aios_status.py record knowledge --query "<phrase>"`.

## Other requests
- "What is in the store?" → `python3 execution/ingest_folder.py --list`.
- "Is the store up to date?" → `python3 execution/ingest_folder.py <folder> --check` (writes nothing).
- "Take <folder> out" → confirm once, then `python3 execution/ingest_folder.py <folder> --remove`.

## Rules
- Never on a schedule and never without the owner's yes for that folder.
- Folders in `aios.json` → `never_ingest` are refused by the tool; never work around it.
- The tool reads `.env` itself. Never read or print `.env`.
