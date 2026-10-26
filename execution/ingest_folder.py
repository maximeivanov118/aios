#!/usr/bin/env python3
"""Put one folder of this AIOS into its Supabase store (public.documents), or take it out again.

Opt-in only. Nothing runs on a schedule; a folder is re-synced only when the owner asks again.
The script reads this AIOS's own .env itself: the calling session never needs to see the key.

usage:  python3 execution/ingest_folder.py <folder> [--dry-run]   # <folder> relative to the AIOS root, or absolute inside it
        python3 execution/ingest_folder.py <folder> --check       # compare the store with disk, write nothing
        python3 execution/ingest_folder.py <folder> --remove      # delete that folder's rows
        python3 execution/ingest_folder.py --list                 # folders currently in the store, with counts

What goes in: text files with an allowed extension (see EXTENSIONS), at most MAX_BYTES each.
What never goes in: anything under a folder listed in aios.json "never_ingest", any .env*, credentials*/token* json, .git, node_modules,
.next*, .tmp, caches, binaries. No flag overrides the deny list.

Idempotent: rows are keyed by (folder, rel_path); unchanged files (same sha256) are skipped; files that
disappeared from disk are deleted from the store; after writing, every row is read back and its sha compared.
HTTPS goes through curl (python.org Python on macOS ships no CA certs). The key goes to curl as a config on stdin:
never on the command line, never in a file. A request body goes through a temp file that is always deleted.
Never ingested either: symlinks (a link can point at .env), and any file whose CONTENT looks like a key or a password.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

PROJECT = Path(__file__).resolve().parent.parent          # the AIOS root
WORKSPACE = PROJECT                                       # ingest never reaches outside the AIOS root
ENV_FILE = PROJECT / ".env"

EXTENSIONS = {"md", "txt", "json", "csv", "yaml", "yml", "html", "toml", "sql", "py", "ts", "tsx", "js"}
MAX_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", ".next", ".next.nosync", ".tmp", "__pycache__", ".venv", "venv",
             ".cache", "dist", "build", ".turbo", ".vercel", ".supabase", ".temp", ".claude-backup"}
def _denied() -> tuple:
    """Folders that never go in, whatever the flags: aios.json \"never_ingest\" plus the fixed ones."""
    fixed = (".claude", "execution", "data/supabase", ".tmp")
    try:
        extra = json.loads((PROJECT / "aios.json").read_text()).get("never_ingest", [])
    except (OSError, json.JSONDecodeError):
        extra = []
    return fixed + tuple(str(x).strip("/") for x in extra)


DENIED_FOLDERS = _denied()
SECRET_CONTENT = re.compile(
    r"sb_secret_[A-Za-z0-9_-]{10,}|sk-ant-[A-Za-z0-9_-]{10,}|\bsk-[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}\b|ghp_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJhbGciOi[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    r"|^\s*[A-Z][A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD|PASSWD)\s*=\s*\S{6,}|\b(password|passwd|mot de passe|wachtwoord)\s*[:=]\s*\S{4,}",
    re.I | re.M)
SECRET_FILE = re.compile(r"(^|/)(\.env(\..*)?|credentials.*\.json|token.*\.json|.*\.pem|.*\.key|.*secret.*)$", re.I)
PAGE = 200


def load_env() -> dict:
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
        if m:
            env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    for k in ("SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        if not env.get(k):
            sys.exit(f"missing {k} in {ENV_FILE}")
    return env


def rest(env: dict, method: str, path: str, body=None, prefer: str = "return=minimal", extra_headers=()):
    """One PostgREST call through curl. Returns (status, parsed json or text)."""
    def q(v: str) -> str:
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    cfg = [f"url = {q(env['SUPABASE_URL'] + '/rest/v1/' + path)}", f"request = {q(method)}",
           f"header = {q('apikey: ' + env['SUPABASE_SECRET_KEY'])}",      # sb_secret_ keys go in apikey only, never in Authorization
           f"header = {q('Content-Type: application/json')}", f"header = {q('Prefer: ' + prefer)}",
           "silent", "show-error", "max-time = 120", 'write-out = "\\n%{http_code}"']
    cfg += [f"header = {q(h)}" for h in extra_headers]
    body_file = None
    try:
        if body is not None:
            fd, body_file = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as bf:
                json.dump(body, bf)
            cfg.append(f"data-binary = {q('@' + body_file)}")
        r = subprocess.run(["curl", "--config", "-"], input="\n".join(cfg), capture_output=True, text=True)
    finally:
        if body_file:
            os.unlink(body_file)
    out, _, code = r.stdout.rpartition("\n")
    if r.returncode != 0 or code.strip() in ("", "000"):
        return 0, (f"no answer from Supabase (curl exit {r.returncode}: {r.stderr.strip()[:200]}). "
                   "Check SUPABASE_URL in .env, the network, and whether the project is paused.")
    try:
        return int(code), (json.loads(out) if out.strip() else None)
    except json.JSONDecodeError:
        return int(code), out


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_folder(arg: str) -> tuple[Path, str]:
    p = Path(arg).expanduser()
    p = (p if p.is_absolute() else WORKSPACE / p).resolve()
    try:
        rel = p.relative_to(WORKSPACE).as_posix()
    except ValueError:
        sys.exit(f"refused: {p} is outside this AIOS ({WORKSPACE}). Copy the files into knowledge/ first.")
    if not p.is_dir():
        sys.exit(f"not a folder: {p}")
    for d in DENIED_FOLDERS:
        if rel == d or rel.startswith(d + "/"):
            sys.exit(f"refused: {rel} is on the deny list ({d}); nothing read, nothing written")
    if rel in ("", "."):
        sys.exit("refused: the whole AIOS is not a folder to ingest; name a subfolder (for example knowledge/sops)")
    return p, rel


def scan(folder: Path, rel_folder: str) -> tuple[list[dict], list[str]]:
    """Return (documents to upsert, skipped reasons)."""
    docs, skipped = [], []
    project = "/".join(rel_folder.split("/")[:2])
    def denied(path: Path) -> bool:
        r = path.relative_to(WORKSPACE).as_posix()
        return any(r == d or r.startswith(d + "/") for d in DENIED_FOLDERS)

    for root, dirs, files in os.walk(folder):                       # os.walk never follows directory symlinks
        keep = []
        for d in sorted(dirs):
            dp = Path(root) / d
            if d in SKIP_DIRS or d.startswith(".claude-backup"):
                continue
            if dp.is_symlink():
                skipped.append(f"symlink         {dp.relative_to(folder).as_posix()}/")
            elif denied(dp):
                skipped.append(f"never-ingest    {dp.relative_to(folder).as_posix()}/")
            else:
                keep.append(d)
        dirs[:] = keep
        for name in sorted(files):
            fp = Path(root) / name
            rel = fp.relative_to(folder).as_posix()
            if fp.is_symlink():
                skipped.append(f"symlink         {rel}")
                continue
            if SECRET_FILE.search(rel):
                skipped.append(f"secret-pattern  {rel}")
                continue
            ext = fp.suffix.lower().lstrip(".")
            if ext not in EXTENSIONS:
                continue
            size = fp.stat().st_size
            if size > MAX_BYTES:
                skipped.append(f"too-large       {rel} ({size} bytes)")
                continue
            try:
                text = fp.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                skipped.append(f"not-utf8        {rel}")
                continue
            if "\x00" in text:
                skipped.append(f"binary          {rel}")
                continue
            if SECRET_CONTENT.search(text):
                skipped.append(f"secret-content  {rel}  (looks like a key or password: remove it from the file, then run again)")
                continue
            title = None
            if ext == "md":
                m = re.search(r"^#\s+(.+)$", text, re.M)
                title = m.group(1).strip() if m else None
            docs.append({
                "folder": rel_folder, "rel_path": rel, "project": project, "kind": ext,
                "title": title or fp.name, "content": text, "size_bytes": size, "content_sha": sha(text),
                "file_mtime": datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).isoformat(),
                "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
            })
    return docs, skipped


def stored(env: dict, rel_folder: str) -> dict:
    """rel_path -> content_sha for every row of this folder."""
    out, offset = {}, 0
    while True:
        code, rows = rest(env, "GET", f"documents?folder=eq.{quote(rel_folder, safe='')}&select=rel_path,content_sha"
                                      f"&order=rel_path&limit={PAGE}&offset={offset}")
        if code != 200:
            sys.exit(f"read failed [{code}]: {rows}")
        for r in rows:
            out[r["rel_path"]] = r["content_sha"]
        if len(rows) < PAGE:
            return out
        offset += PAGE


def upsert(env: dict, docs: list[dict]) -> None:
    for i in range(0, len(docs), 50):
        code, body = rest(env, "POST", "documents?on_conflict=folder,rel_path", docs[i:i + 50],
                          prefer="resolution=merge-duplicates,return=minimal")
        if code not in (200, 201, 204):
            sys.exit(f"upsert failed [{code}]: {str(body)[:300]}")


def delete_paths(env: dict, rel_folder: str, paths: list[str]) -> None:
    for i in range(0, len(paths), 50):
        chunk = ",".join('"' + p.replace('"', '\\"') + '"' for p in paths[i:i + 50])
        safe_chars = '(),"'
        in_list = quote(chunk, safe=safe_chars)
        code, body = rest(env, "DELETE", f"documents?folder=eq.{quote(rel_folder, safe='')}&rel_path=in.({in_list})")
        if code not in (200, 204):
            sys.exit(f"delete failed [{code}]: {str(body)[:300]}")


def verify(env: dict, rel_folder: str, docs: list[dict]) -> bool:
    have = stored(env, rel_folder)
    want = {d["rel_path"]: d["content_sha"] for d in docs}
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    changed = sorted(p for p in want if p in have and have[p] != want[p])
    for p in missing: print(f"  MISSING in store  {p}")
    for p in extra:   print(f"  EXTRA in store    {p}")
    for p in changed: print(f"  SHA MISMATCH      {p}")
    print(f"verify {rel_folder}: disk={len(want)} store={len(have)} missing={len(missing)} extra={len(extra)} mismatched={len(changed)}")
    return not (missing or extra or changed)


def list_folders(env: dict) -> None:
    rows, offset = [], 0
    while True:                                   # PostgREST caps a response (1000 rows by default): page through
        code, page = rest(env, "GET", f"documents?select=folder,ingested_at&order=id&limit={PAGE}&offset={offset}")
        if code != 200:
            sys.exit(f"read failed [{code}]: {page}")
        rows += page
        if len(page) < PAGE:
            break
        offset += PAGE
    agg = {}
    for r in rows:
        a = agg.setdefault(r["folder"], [0, r["ingested_at"]])
        a[0] += 1
        a[1] = max(a[1], r["ingested_at"])
    if not agg:
        print("store is empty: no folder has been put into Supabase yet")
    for f, (n, last) in sorted(agg.items()):
        print(f"{n:5d}  {f}   (last ingest {last[:19]})")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    env = load_env()
    if "--list" in flags:
        return list_folders(env)
    if len(args) != 1:
        sys.exit(__doc__)
    folder, rel_folder = resolve_folder(args[0])

    if "--remove" in flags:
        have = stored(env, rel_folder)
        if not have:
            print(f"nothing stored for {rel_folder}")
            return
        delete_paths(env, rel_folder, sorted(have))
        left = stored(env, rel_folder)
        print(f"removed {len(have)} documents for {rel_folder}; remaining={len(left)}")
        sys.exit(1 if left else 0)

    docs, skipped = scan(folder, rel_folder)
    for s in skipped:
        print(f"  skip {s}")
    if "--check" in flags:
        sys.exit(0 if verify(env, rel_folder, docs) else 1)

    have = stored(env, rel_folder)
    want = {d["rel_path"]: d for d in docs}
    to_write = [d for p, d in want.items() if have.get(p) != d["content_sha"]]
    to_delete = sorted(set(have) - set(want))
    print(f"{rel_folder}: {len(docs)} files on disk, {len(have)} in store -> write {len(to_write)}, delete {len(to_delete)}, unchanged {len(docs) - len(to_write)}")
    if "--dry-run" in flags:
        for d in to_write[:30]:
            print(f"  + {d['rel_path']} ({d['size_bytes']} bytes)")
        if len(to_write) > 30:
            print(f"  … {len(to_write) - 30} more")
        for p in to_delete:
            print(f"  - {p}")
        return
    if to_write:
        upsert(env, to_write)
    if to_delete:
        delete_paths(env, rel_folder, to_delete)
    sys.exit(0 if verify(env, rel_folder, docs) else 1)


if __name__ == "__main__":
    main()
