"""Back up the AIOS Supabase store to local JSON, and prove that a backup restores.

usage: python3 execution/backup_db.py                         # new backup -> ~/.local/share/aios-backups/<project ref>/<UTC stamp>/
       python3 execution/backup_db.py --restore-test [<dir>]  # default: the newest backup
       python3 execution/backup_db.py --list

What is backed up: every table in the schemas public and private, all rows, all columns except generated
ones (the `search` tsvectors: Postgres recomputes them on insert). What is not: the schema (it lives in
data/supabase/migrations/, in git) and auth.users (Supabase owns that schema).

Each page of 200 rows is written with the row count and an md5 that Postgres computed over the same rows in the
same query. --restore-test loads each page into a temp table inside a transaction that ends with RAISE EXCEPTION,
so nothing persists, and passes only when the restored count and md5 equal the backup's.

Where: OUTSIDE this AIOS folder on purpose (not synced, not in git). To delete every backup of this store:
remove ~/.local/share/aios-backups/<project ref>/. A passed --restore-test leaves RESTORE_TEST_PASSED in the backup
folder; security_check.py only counts backups that carry it.

Safety: the folder is 0700 and the files 0600, outside any synced folder and outside git. One subfolder per project
ref, so two AIOS stores on the same machine never share a backup folder. The newest 14 backups are kept. The backup
holds personal data (D3): a person deleted from the store stays in the backups for up to 14 more backups.
"""
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_mgmt import load_env, management_sql  # noqa: E402

ROOT = Path(os.path.expanduser("~/.local/share/aios-backups")) / (load_env().get("SUPABASE_PROJECT_REF") or "no-ref")
SCHEMAS = ("public", "private")
PAGE = 200
KEEP = 14


def q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def sql_rows(query: str) -> list:
    code, body = management_sql(query)
    if not code.startswith("2"):
        raise SystemExit(f"query failed http={code}: {body[:400]}")
    return json.loads(body)


def tables() -> list[dict]:
    """Every table with its non-generated columns and its primary-key columns."""
    schemas = ",".join(f"'{s}'" for s in SCHEMAS)
    return sql_rows(f"""
      select n.nspname as schema, c.relname as name,
        (select json_agg(a.attname order by a.attnum) from pg_attribute a
          where a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped and a.attgenerated = '') as cols,
        (select json_agg(a.attname order by array_position(i.indkey::int2[], a.attnum)) from pg_index i
          join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
          where i.indrelid = c.oid and i.indisprimary) as pk
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
      where c.relkind in ('r', 'p') and n.nspname in ({schemas})
      order by 1, 2""")


def write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def backup() -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    os.chmod(ROOT.parent, 0o700)
    os.chmod(ROOT, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / stamp
    out.mkdir(mode=0o700)
    manifest = {"created_at": stamp, "schemas": SCHEMAS, "page_size": PAGE, "tables": []}
    try:
        _backup_into(out, manifest)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)      # a half backup must never look like a backup
        raise
    for old in sorted(p for p in ROOT.iterdir() if p.is_dir())[:-KEEP]:
        shutil.rmtree(old)
    print(f"backup {out}  ({sum(e['rows'] for e in manifest['tables'])} rows, {len(manifest['tables'])} tables)")
    print("next: python3 execution/backup_db.py --restore-test   (a backup counts only after it passes)")
    return out


def _backup_into(out: Path, manifest: dict) -> None:
    for t in tables():
        cols = ", ".join(q(c) for c in t["cols"])
        order = ", ".join(q(c) for c in (t["pk"] or t["cols"]))
        entry = {"table": f"{t['schema']}.{t['name']}", "cols": t["cols"], "pages": [], "rows": 0}
        offset = 0
        while True:
            row = sql_rows(f"""
              select count(*)::int as n,
                     coalesce(md5(string_agg(t::text, E'\\n' order by t::text)), '') as md5,
                     coalesce(json_agg(t), '[]'::json)::text as rows
              from (select {cols} from {q(t['schema'])}.{q(t['name'])} order by {order}
                    limit {PAGE} offset {offset}) t""")[0]
            if row["n"] == 0 and offset > 0:
                break
            # Postgres returns the page as JSON *text*, written verbatim: parsing it in Python would turn
            # numeric values into floats (4.50 -> 4.5) and the restore md5 would no longer match.
            data = row["rows"].encode()
            name = f"{t['schema']}.{t['name']}.p{offset // PAGE:04d}.json"
            write_private(out / name, data)
            entry["pages"].append({"file": name, "n": row["n"], "md5": row["md5"], "sha256": hashlib.sha256(data).hexdigest()})
            entry["rows"] += row["n"]
            offset += PAGE
            if row["n"] < PAGE:
                break
        manifest["tables"].append(entry)
        print(f"  {entry['table']:<36} {entry['rows']:>6} rows  {len(entry['pages'])} page(s)")
    write_private(out / "manifest.json", json.dumps(manifest, indent=1).encode())


def restore_test(folder: Path) -> bool:
    manifest = json.loads((folder / "manifest.json").read_text())
    ok = True
    for entry in manifest["tables"]:
        schema, name = entry["table"].split(".", 1)
        cols = ", ".join(q(c) for c in entry["cols"])
        for page in entry["pages"]:
            data = (folder / page["file"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != page["sha256"]:
                print(f"BAD  {page['file']}: file changed since the backup (sha256)")
                ok = False
                continue
            tag = "bk_" + secrets.token_hex(8)
            body = data.decode()
            assert f"${tag}$" not in body
            code, text = management_sql(f"""
              do ${tag}_do$ declare n int; h text;
              begin
                create temp table r on commit drop as select {cols} from {q(schema)}.{q(name)} with no data;
                insert into r select * from json_populate_recordset(null::r, ${tag}${body}${tag}$::json);
                select count(*), coalesce(md5(string_agg(x::text, E'\\n' order by x::text)), '') into n, h from r x;
                raise exception 'RESTORE_RESULT %|%', n, h;
              end ${tag}_do$;""")
            m = re.search(r"RESTORE_RESULT (\d+)\|([0-9a-f]*)", text)
            if not m:
                print(f"BAD  {page['file']}: no result (http={code}) {text[:300]}")
                ok = False
                continue
            same = int(m.group(1)) == page["n"] and m.group(2) == page["md5"]
            ok &= same
            print(f"{'OK ' if same else 'BAD'}  {page['file']:<44} {m.group(1):>4} rows  md5 {m.group(2)[:12]}")
    marker = folder / "RESTORE_TEST_PASSED"
    if ok:
        marker.write_text(datetime.now(timezone.utc).isoformat() + "\n")
    elif marker.exists():
        marker.unlink()
    print("RESTORE TEST", "PASSED" if ok else "FAILED", f"— {folder}")
    return ok


def main():
    args = sys.argv[1:]
    if "--list" in args:
        for p in sorted(ROOT.iterdir()) if ROOT.exists() else []:
            print(p)
        return
    if "--restore-test" in args:
        rest = [a for a in args if a != "--restore-test"]
        folder = Path(rest[0]) if rest else max(p for p in ROOT.iterdir() if p.is_dir())
        sys.exit(0 if restore_test(folder) else 1)
    backup()


if __name__ == "__main__":
    main()
