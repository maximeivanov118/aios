"""Security gate for this AIOS's Supabase project: every control of directives/supabase_security_baseline.md, read live.

usage: python3 execution/security_check.py        # exit 0 only when every control passes

Read-only. Settings come from the Management API (GET only). The RLS break test runs inside a transaction that
rolls itself back. Key probes are GET requests to the Data API. No secret value is printed.
Fix steps for a FAIL: directives/supabase_security_baseline.md (stage 2 of /aios walks them).
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_mgmt import PROJECT, curl, load_env, management_get, management_sql  # noqa: E402

results = []


def check(control: str, ok: bool, detail: str) -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {control:<44} {detail}")


def get_json(path: str):
    code, body = management_get(path)
    if not code.startswith("2"):
        return None, f"http={code}"
    return json.loads(body), ""


def data_api_status(key: str, table: str) -> str:
    env = load_env()
    cfg = [f'url = "{env["SUPABASE_URL"]}/rest/v1/{table}?select=*&limit=1"', f'header = "apikey: {key}"', "max-time = 30"]
    if not key.startswith("sb_"):
        cfg.append(f'header = "Authorization: Bearer {key}"')
    return curl(cfg)[0]


def evaluate_breaktest(r: dict) -> tuple:
    """The verdict on data/tests/rls_break_test.sql's result. Shared with the kit's local test harness."""
    tables = sorted(k[5:] for k in r if k.startswith("real_"))
    stranger = all(r[f"stranger_{t}"] == 0 for t in tables)
    owner = all(r[f"owner_{t}"] == r[f"real_{t}"] for t in tables)
    closed = all(r[k] == "refused" for k in ("owner_insert", "anon_insert", "anon_items", "anon_search"))
    new_obj = (r["new_table_rls"] is True and not r["new_table_anon_select"] and not r["new_table_auth_select"]
               and not r["new_fn_anon_exec"] and not r["new_fn_auth_exec"])
    probes = all(r[f"real_{t}"] > 0 for t in ("sources", "items", "documents"))
    structure = not r["open_policies"] and not r["anon_table_grants"] and not r["anon_functions"]
    return (stranger and owner and closed and new_obj and probes and structure,
            f"stranger 0 rows={stranger} owner sees all={owner} writes/anon refused={closed} new tables+functions closed={new_obj}"
            f" probe rows={probes} open policies={r['open_policies'] or 'none'} anon grants={r['anon_table_grants'] or 'none'}"
            f" anon functions={r['anon_functions'] or 'none'}")


def main():
    env = load_env()

    auth, err = get_json("/config/auth")
    if auth is None:
        check("Auth settings readable", False, err)
    else:
        check("Sign-ups closed", auth.get("disable_signup") is True, f"disable_signup={auth.get('disable_signup')}")
        check("Anonymous sign-ins off", auth.get("external_anonymous_users_enabled") is False, "")
        n = auth.get("password_min_length") or 0
        check("Minimum password length >= 12", n >= 12, f"now {n}")
        check("Re-authentication for password change", auth.get("security_update_password_require_reauthentication") is True, "")

    legacy, err = get_json("/api-keys/legacy")
    check("Legacy JWT API keys disabled", legacy is not None and legacy.get("enabled") is False, err or f"enabled={legacy.get('enabled')}")

    keys, err = get_json("/config/auth/signing-keys")
    live_hs = [k["status"] for k in (keys or {}).get("keys", []) if k.get("algorithm") == "HS256" and k.get("status") != "revoked"]
    check("Legacy HS256 signing key revoked", keys is not None and not live_hs, err or (f"HS256 status {live_hs}" if live_hs else "revoked"))

    if env.get("SUPABASE_SERVICE_ROLE_KEY"):
        status = data_api_status(env["SUPABASE_SERVICE_ROLE_KEY"], "items")
        check("Old service_role key returns 401", status == "401", f"http={status}")
    else:
        check("Old service_role key returns 401", True, "n/a: no legacy key in .env (keep it that way)")

    if env.get("SUPABASE_PUBLISHABLE_KEY"):
        status = data_api_status(env["SUPABASE_PUBLISHABLE_KEY"], "items")
        check("Publishable key cannot read tables", status in ("401", "403"), f"http={status}")

    ssl, err = get_json("/ssl-enforcement")
    check("SSL enforced on direct connections", ssl is not None and ssl.get("currentConfig", {}).get("database") is True, err)

    net, err = get_json("/network-restrictions")
    cidrs = (net or {}).get("config", {})
    open_ = "0.0.0.0/0" in (cidrs.get("dbAllowedCidrs") or []) or "::/0" in (cidrs.get("dbAllowedCidrsV6") or [])
    check("Direct connections limited to an allowlist", net is not None and not open_,
          err or f"v4 {cidrs.get('dbAllowedCidrs')} v6 {cidrs.get('dbAllowedCidrsV6')}")

    adv, err = get_json("/advisors/security")
    bad = [f"{l['level']} {l['name']}" for l in (adv or {}).get("lints", []) if l.get("level") in ("ERROR", "WARN")]
    check("Security Advisor: 0 ERROR, 0 WARN", adv is not None and not bad, err or (", ".join(bad) if bad else "clean"))

    code, text = management_sql((PROJECT / "data" / "tests" / "rls_break_test.sql").read_text())
    try:
        msg = json.loads(text).get("message", "") if text.strip().startswith("{") else text
        found = re.search(r"BREAKTEST (\{.*\})", msg, re.S)
        if not found:
            check("RLS break test (rolled back)", False, f"the test itself failed (http={code}): {' '.join(msg.split())[:220]}")
        else:
            ok, detail = evaluate_breaktest(json.loads(found.group(1)))
            check("RLS break test (rolled back)", ok, detail)
    except (KeyError, json.JSONDecodeError) as e:
        check("RLS break test (rolled back)", False, f"no result: http={code} {e}")

    root = Path(os.path.expanduser("~/.local/share/aios-backups")) / env["SUPABASE_PROJECT_REF"]
    proven = [p for p in root.iterdir() if p.is_dir() and (p / "RESTORE_TEST_PASSED").exists()] if root.exists() else []
    newest = max(proven, default=None, key=lambda p: (p / "RESTORE_TEST_PASSED").stat().st_mtime)
    age_days = (time.time() - (newest / "RESTORE_TEST_PASSED").stat().st_mtime) / 86400 if newest else None
    check("Backup restore-tested, newer than 8 days", newest is not None and age_days < 8,
          f"{newest.name} ({age_days:.1f} days)" if newest else "no restore-tested backup: run backup_db.py, then backup_db.py --restore-test")

    passed = sum(results)
    print(f"\n{'GATE PASSED' if all(results) else 'GATE FAILED'} — {passed}/{len(results)} controls pass")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
