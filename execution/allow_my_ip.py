"""Allow only this machine's current public IP to open direct Postgres connections to this AIOS's Supabase project.

Run it before any command that connects to Postgres directly (`supabase db push`, `supabase migration list`).
It reads your public IPv4 (and IPv6 when the network has one) and REPLACES the project's allowlist with those
addresses: IPv4 as /32, IPv6 as /64 (macOS rotates the last 64 bits of its IPv6 address). When nothing changed
it does nothing. It reaches Supabase through the Management API over HTTPS, which the allowlist does not cover,
so it cannot lock you out. The Data API (PostgREST), Auth and Storage are not affected by the allowlist at all.

usage: python3 execution/allow_my_ip.py            # apply when the address changed
       python3 execution/allow_my_ip.py --check    # print current vs wanted, change nothing
       python3 execution/allow_my_ip.py --open     # undo: back to 0.0.0.0/0 and ::/0

Token: SUPABASE_NETWORK_TOKEN from this project's .env (an access token with only
database_network_restrictions_read + _write), falling back to SUPABASE_ACCESS_TOKEN. The write goes through the
official CLI (`supabase network-restrictions update`); the token is passed in its environment, never on argv.
No CLI installed: set the same allowlist in the dashboard (Database > Settings > Network restrictions).
"""
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_mgmt import load_env  # noqa: E402

CLI = shutil.which("supabase") or os.path.expanduser("~/.local/bin/supabase")


def token(env: dict) -> str:
    t = env.get("SUPABASE_NETWORK_TOKEN") or env.get("SUPABASE_ACCESS_TOKEN")
    if not t:
        sys.exit("missing SUPABASE_NETWORK_TOKEN (or SUPABASE_ACCESS_TOKEN) in this AIOS folder's .env")
    return t


def public_ip(flag: str, url: str):
    out = subprocess.run(["curl", flag, "-s", "--max-time", "8", url], capture_output=True, text=True)
    value = out.stdout.strip()
    try:
        return ipaddress.ip_address(value) if out.returncode == 0 and value else None
    except ValueError:
        return None


def wanted() -> tuple[list[str], list[str]]:
    v4 = public_ip("-4", "https://api.ipify.org")
    v6 = public_ip("-6", "https://api64.ipify.org")
    if v4 is None:
        sys.exit("could not read this machine's public IPv4 address (offline?)")
    cidr4 = [f"{v4}/32"]
    cidr6 = [str(ipaddress.ip_network(f"{v6}/64", strict=False))] if v6 is not None and v6.version == 6 else []
    return cidr4, cidr6


def current(env: dict) -> dict:
    cfg = [f'url = "https://api.supabase.com/v1/projects/{env["SUPABASE_PROJECT_REF"]}/network-restrictions"',
           f'header = "Authorization: Bearer {token(env)}"', "silent", "show-error", "max-time = 30",
           'write-out = "\\n%{http_code}"']
    out = subprocess.run(["curl", "--config", "-"], input="\n".join(cfg), capture_output=True, text=True)
    body, _, code = out.stdout.rpartition("\n")
    if not code.startswith("2"):
        sys.exit(f"reading network restrictions failed: http={code} {body[:300]}")
    return json.loads(body)


def apply(env: dict, cidrs: list[str]) -> None:
    if not os.path.exists(CLI):
        sys.exit("Supabase CLI not found. Install it, or set the allowlist in the dashboard: "
                 "Database > Settings > Network restrictions, with: " + ", ".join(cidrs))
    cmd = [CLI, "network-restrictions", "update", "--project-ref", env["SUPABASE_PROJECT_REF"], "--experimental"]
    for c in cidrs:
        cmd += ["--db-allow-cidr", c]
    if any(c in ("0.0.0.0/0", "::/0") for c in cidrs):
        cmd.append("--bypass-cidr-checks")
    run_env = {**os.environ, "SUPABASE_ACCESS_TOKEN": token(env)}
    out = subprocess.run(cmd, capture_output=True, text=True, env=run_env)
    if out.returncode != 0 or "403" in out.stdout + out.stderr:
        sys.exit("update refused: " + (out.stdout + out.stderr).strip()[-400:] +
                 "\n→ create an access token with database_network_restrictions_read + _write and add it to "
                 "this AIOS folder's .env as SUPABASE_NETWORK_TOKEN")


def main():
    env = load_env()
    now = current(env)["config"]
    have4, have6 = sorted(now.get("dbAllowedCidrs") or []), sorted(now.get("dbAllowedCidrsV6") or [])
    if "--open" in sys.argv:
        want4, want6 = ["0.0.0.0/0"], ["::/0"]
    else:
        want4, want6 = wanted()
    print(f"allowed now : v4 {have4}  v6 {have6}")
    print(f"wanted      : v4 {sorted(want4)}  v6 {sorted(want6)}")
    if (have4, have6) == (sorted(want4), sorted(want6)):
        print("no change needed")
        return
    if "--check" in sys.argv:
        print("--check: would change the allowlist (run without --check to apply)")
        sys.exit(2)
    apply(env, want4 + want6)
    for _ in range(20):                                   # wait until Supabase reports the new list as applied
        state = current(env)
        cfg = state["config"]
        if (sorted(cfg.get("dbAllowedCidrs") or []), sorted(cfg.get("dbAllowedCidrsV6") or [])) == (sorted(want4), sorted(want6)) \
                and state.get("status") == "applied":
            print("applied")
            return
        time.sleep(3)
    sys.exit(f"the new allowlist is not reported as applied yet: {state}")


if __name__ == "__main__":
    main()
