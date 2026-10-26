# Directive: put company knowledge into the store

**Goal:** a folder of documents becomes searchable in the store, exactly as it is on disk, and nothing else goes in.
**Trigger:** the owner says "put <folder> into Supabase" (or runs `/knowledge-ingest <folder>`). Never on a schedule, never "everything".
**Tool:** `execution/ingest_folder.py` (one row per file in `public.documents`, keyed by folder + path).

## Steps
1. **Check the folder.** It must be inside this AIOS (normally `knowledge/<topic>`). Files from elsewhere are copied into `knowledge/` first.
2. **Convert what is not text.** `.docx` / `.pptx` → `python3 execution/convert_docs.py <file or folder> --out knowledge/<topic>` (`--out` is required). PDF → Claude reads it page by page and writes one Markdown file per document, with a `# Title`. Excel → export CSV from Excel.
3. **Remove what must not go in.** Personal data the owner has no right to store, passwords, bank details. The tool refuses secret-looking file names, but it cannot read meaning.
4. **Dry run:** `python3 execution/ingest_folder.py <folder> --dry-run`. Show the owner the count and the list. Continue only on their yes.
5. **Run:** `python3 execution/ingest_folder.py <folder>`. It writes, reads every row back and compares sha256. It must end with `missing=0 extra=0 mismatched=0`.
6. **Prove it is findable:** `python3 execution/search_store.py "<a phrase from one of the files>"` must show that file.
7. **Log it:** the first time, `aios_status.py record knowledge --query "<that phrase>"`.

## Updating and removing
- Same command again after edits: only changed files are written, files deleted on disk are deleted from the store.
- `--check` compares store and disk and writes nothing. `--remove` deletes the folder's rows. `--list` shows what is in.
- A folder in `aios.json` → `never_ingest` is refused whatever the flags.

## Edge cases
- Files above 2 MB are skipped (split them). Non-UTF-8 text is skipped (re-save as UTF-8).
- Search ranks titles first: a file with a clear `# Title` is found far more easily.
- A document that needs real columns (a price list you want to filter, a customer table) deserves its own table: write a migration instead.

## Change log
- Shipped with the shared AIOS: an update replaces this file. Lessons about it go in `tasks/lessons.md`.
