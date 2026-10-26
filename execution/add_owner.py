"""Make a Supabase Auth user an owner of this AIOS store (the only people who can read it through the app or API).

usage: python3 execution/add_owner.py owner@company.com          # add (the user must exist: dashboard > Authentication > Add user)
       python3 execution/add_owner.py --list                     # who is an owner now

Writes one row in private.owners through the Management API. Prints e-mails and dates only, no ids, no keys.
"""
import json
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_mgmt import management_sql  # noqa: E402


def lit(text: str) -> str:
    tag = "e_" + secrets.token_hex(6)
    return f"${tag}${text}${tag}$"


def sql(query: str) -> list:
    code, body = management_sql(query)
    if not code.startswith("2"):
        sys.exit(f"failed: http={code} {body[:300]}")
    return json.loads(body)


def main() -> None:
    if "--list" in sys.argv or len(sys.argv) < 2:
        rows = sql("select u.email, o.added_at::date::text as added from private.owners o join auth.users u on u.id = o.user_id order by 2")
        print("\n".join(f"{r['added']}  {r['email']}" for r in rows) or "no owner yet: nobody can read the store through the API (safe, but the app will show nothing)")
        return
    email = sys.argv[1].strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        sys.exit(f"not an e-mail address: {email}")
    found = sql(f"select count(*)::int as n from auth.users where lower(email) = {lit(email)}")[0]["n"]
    if not found:
        sys.exit(f"no Auth user {email}. Create it first: Supabase dashboard > Authentication > Users > Add user "
                 "(password of 12+ characters), then run this again.")
    sql(f"insert into private.owners (user_id, note) select id, 'added by add_owner.py' from auth.users "
        f"where lower(email) = {lit(email)} on conflict (user_id) do nothing")
    print(f"{email} is an owner")


if __name__ == "__main__":
    main()
