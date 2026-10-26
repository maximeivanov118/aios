"""Shared helper: call the Supabase Management API for this AIOS's Supabase project with the token from this project's .env.

HTTPS goes through curl (python.org Python on macOS ships no CA certs). The token is passed to curl on stdin,
never on the command line, and is never printed.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent          # the AIOS root (execution/ sits directly in it)


def load_env() -> dict:
    env = {}
    env_file = PROJECT / ".env"
    if not env_file.exists():
        raise SystemExit(f"no .env in {PROJECT}: copy .env.example to .env and fill it (stage 2 of /aios)")
    for line in env_file.read_text().splitlines():
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
        if m:
            env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


def curl(cfg: list[str]) -> tuple[str, str]:
    """Run curl with a config on stdin. Returns (http_code, body)."""
    out = subprocess.run(["curl", "--config", "-"], input="\n".join(cfg + ["silent", "show-error", 'write-out = "\\n%{http_code}"']),
                         capture_output=True, text=True)
    body, _, code = out.stdout.rpartition("\n")
    if out.returncode != 0:
        body = f"curl exit {out.returncode}: {out.stderr.strip()} {body}"
    return code, body


def management_get(path: str) -> tuple[str, str]:
    """GET /v1/projects/{ref}<path>. Returns (http_code, body). The caller must not print secret fields."""
    env = load_env()
    return curl([f'url = "https://api.supabase.com/v1/projects/{env["SUPABASE_PROJECT_REF"]}{path}"',
                 f'header = "Authorization: Bearer {env["SUPABASE_ACCESS_TOKEN"]}"', "max-time = 60"])


def management_sql(query: str, timeout: int = 120) -> tuple[str, str]:
    """POST /v1/projects/{ref}/database/query. Returns (http_code, body)."""
    env = load_env()
    for k in ("SUPABASE_ACCESS_TOKEN", "SUPABASE_PROJECT_REF"):
        if not env.get(k):
            raise SystemExit(f"missing {k} in {PROJECT / '.env'}")
    fd, payload = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump({"query": query}, f)
    cfg = [f'url = "https://api.supabase.com/v1/projects/{env["SUPABASE_PROJECT_REF"]}/database/query"',
           'request = "POST"', f'header = "Authorization: Bearer {env["SUPABASE_ACCESS_TOKEN"]}"',
           'header = "Content-Type: application/json"', f'data-binary = "@{payload}"',
           "silent", "show-error", f"max-time = {timeout}", 'write-out = "\\n%{http_code}"']
    try:
        out = subprocess.run(["curl", "--config", "-"], input="\n".join(cfg), capture_output=True, text=True)
    finally:
        os.unlink(payload)
    body, _, code = out.stdout.rpartition("\n")
    if out.returncode != 0:
        body = f"curl exit {out.returncode}: {out.stderr.strip()} {body}"
    return code, body
