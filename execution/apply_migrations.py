"""Apply data/supabase/migrations/*.sql to this AIOS's Supabase project, in order, through the Management API.

usage: python3 execution/apply_migrations.py            # apply every pending migration, stop at the first failure
       python3 execution/apply_migrations.py --check    # compare disk with the project; exit 1 if anything differs

No Supabase CLI and no database password needed: SUPABASE_ACCESS_TOKEN (scopes: database + migrations) and
SUPABASE_PROJECT_REF from this AIOS's .env. Each migration runs in ONE transaction together with its row in
supabase_migrations.schema_migrations, the table the Supabase CLI uses, so `supabase migration list` agrees.
A failing migration leaves nothing behind (a failing batch through this endpoint is rolled back whole).

Rules: never edit a migration that is applied, write a new one. Never change the schema in the dashboard.
After applying: python3 execution/security_check.py must print GATE PASSED.
"""
import json
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_mgmt import PROJECT, management_sql  # noqa: E402

MIGRATIONS = PROJECT / "data" / "supabase" / "migrations"
BOOTSTRAP = """create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);"""


def on_disk() -> list[tuple[str, str, Path]]:
    out = []
    for p in sorted(MIGRATIONS.glob("*.sql")):
        m = re.match(r"^(\d+)_(.+)\.sql$", p.name)
        if not m:
            sys.exit(f"bad migration file name (want <digits>_<name>.sql): {p.name}")
        out.append((m.group(1), m.group(2), p))
    return out


def applied() -> dict[str, str]:
    code, body = management_sql(BOOTSTRAP + "\nselect version, name from supabase_migrations.schema_migrations order by version;")
    if not code.startswith("2"):
        sys.exit(f"cannot read the migration history: http={code} {body[:300]}")
    return {r["version"]: r["name"] for r in json.loads(body)}


def quote(text: str) -> str:
    tag = "m_" + secrets.token_hex(6)
    assert f"${tag}$" not in text
    return f"${tag}${text}${tag}$"


def main() -> None:
    disk = on_disk()
    done = applied()
    pending = [(v, n, p) for v, n, p in disk if v not in done]
    unknown = sorted(set(done) - {v for v, _, _ in disk})
    for v, n, _ in disk:
        print(f"{'applied' if v in done else 'PENDING'}  {v}_{n}")
    for v in unknown:
        print(f"UNKNOWN  {v}_{done[v]}  (applied on the project, missing on disk: someone changed the schema elsewhere)")
    if "--check" in sys.argv:
        sys.exit(1 if pending or unknown else 0)
    if unknown:
        sys.exit("stopped: the project has migrations this folder does not know. Find them before applying more.")
    if not pending:
        print("nothing to apply")
        return
    for v, n, p in pending:
        sql = p.read_text(encoding="utf-8")
        batch = (f"begin;\n{sql}\n;\ninsert into supabase_migrations.schema_migrations (version, name, statements) "
                 f"values ({quote(v)}, {quote(n)}, array[{quote(sql)}]);\ncommit;")
        code, body = management_sql(batch, timeout=300)
        if not code.startswith("2"):
            sys.exit(f"FAILED   {v}_{n}: http={code} {body[:500]}\nNothing of this migration was kept. Fix it, then run again.")
        print(f"APPLIED  {v}_{n}")
    left = [v for v, _, _ in on_disk() if v not in applied()]
    print("all migrations applied" if not left else f"still pending: {left}")
    sys.exit(1 if left else 0)


if __name__ == "__main__":
    main()
