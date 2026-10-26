"""Search this AIOS's store from the terminal: company knowledge (documents) and, with --items, mail / events.

usage: python3 execution/search_store.py "pricing for the premium package"
       python3 execution/search_store.py "invoice overdue" --items --n 5

Same ranking as the app and the MCP: full-text match x recency (documents half-life 90 days, items 30 days).
Runs as postgres through the Management API (SUPABASE_ACCESS_TOKEN), so it is the owner's own tool, never a
service for other people. Prints the title, the path and a short highlighted snippet per hit.
The Supabase MCP (read-only) is the normal way for Claude to read the store; this script is the fallback
when the MCP is not authorised yet, and the test that stage 3 of /aios uses ("can we find what we put in?").
"""
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_mgmt import management_sql  # noqa: E402


def lit(text: str) -> str:
    tag = "q_" + secrets.token_hex(6)
    return f"${tag}${text}${tag}$"


def main() -> None:
    argv, n, args = sys.argv[1:], 8, []
    i = 0
    while i < len(argv):
        if argv[i] == "--n" and i + 1 < len(argv):
            n, i = int(argv[i + 1]), i + 2
            continue
        if not argv[i].startswith("--"):
            args.append(argv[i])
        i += 1
    if not args:
        sys.exit(__doc__)
    q = lit(" ".join(args))
    if "--items" in sys.argv:
        sql = f"""select s.occurred_at::date::text as date, s.kind, s.author, s.title, round(s.rank::numeric, 3)::text as rank
                  from public.search_items({q}, 30, {n}) s"""
    else:
        sql = f"""select s.folder || '/' || s.rel_path as path, s.title, round(s.rank::numeric, 3)::text as rank,
                         ts_headline('simple', d.content, websearch_to_tsquery('simple', {q}),
                                     'MaxFragments=1, MaxWords=18, MinWords=8, StartSel=**, StopSel=**') as snippet
                  from public.search_documents({q}, 90, {n}) s join public.documents d on d.id = s.id
                  order by s.rank desc"""
    code, body = management_sql(sql)
    if not code.startswith("2"):
        sys.exit(f"search failed: http={code} {body[:300]}")
    rows = json.loads(body)
    if not rows:
        print("no match")
        sys.exit(1)
    for r in rows:
        if "path" in r:
            print(f"[{r['rank']}] {r['title']}  —  {r['path']}\n        {' '.join(r['snippet'].split())}")
        else:
            print(f"[{r['rank']}] {r['date']} {r['kind']:<7} {r['author'] or '':<24} {r['title'] or ''}")


if __name__ == "__main__":
    main()
