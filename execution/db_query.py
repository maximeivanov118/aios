"""Run one SQL file against the AIOS Supabase project through the Management API, as postgres.

usage: python3 execution/db_query.py <file.sql>

For audits and rolled-back proofs (data/tests/*.sql), not for schema changes: those are migrations.
A test that ends with RAISE EXCEPTION 'BREAKTEST ...' / 'RESTORE_RESULT ...' rolls itself back; this script
prints the message it carried. Token: SUPABASE_ACCESS_TOKEN from this project's .env, passed to curl on stdin.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_mgmt import management_sql  # noqa: E402


def main():
    code, text = management_sql(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        message = json.loads(text).get("message", "") if text.strip().startswith("{") else ""
    except json.JSONDecodeError:
        message = ""
    m = re.search(r"BREAKTEST (\{.*\})", message, re.S)
    if m:
        result = json.loads(m.group(1))
        for k in sorted(result):
            print(f"{k:28} {result[k]}")
        return
    print(f"http={code}\n{text}")
    if not code.startswith("2"):
        sys.exit(1)


if __name__ == "__main__":
    main()
