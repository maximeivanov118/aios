# knowledge/

The company documents that go into the store (stage 3 of `/aios`). One subfolder per topic:

```
knowledge/
├── offers/       price lists, packages, proposals that won
├── sops/         how things are done, step by step
├── faq/          questions customers ask, with the real answers
├── customers/    customer types, objections, case studies (no personal data without the people's consent)
└── company/      about us, values, brand voice, history
```

- Text only: Markdown, text, CSV, JSON, HTML. Word and PowerPoint files are converted first (`python3 execution/convert_docs.py`). Claude converts PDFs page by page into Markdown.
- One topic per file, a clear `# Title` on the first line: search ranks titles highest.
- No passwords, keys or bank details. Files named like `.env`, `credentials*.json`, `*secret*` are refused by the ingest tool anyway.
- Put a folder in with `/knowledge-ingest knowledge/<subfolder>`. Change a file and run it again: only changed files are sent, deleted files are removed from the store.
