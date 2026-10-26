#!/usr/bin/env python3
"""AIOS secret guard (PreToolUse hook). Blocks any tool call that would show the contents of a .env file to Claude.

The kit's scripts read .env themselves, so Claude never needs to. Allowed, because they never print a value:
  grep -oE '^[A-Z0-9_]+' <path>/.env                  key NAMES only
  grep '^KEY=' <path>/.env >> <path>/.env             one key copied file to file (/setup)
  cp <path>/.env.example <path>/.env                  creating the file
  ls / test -f / git status / git check-ignore         file names, never contents
Everything else that names a .env file (cat, head, grep, sed, python -c, Read, Grep, Edit, Write) is refused.
Exit 2 = blocked; the message goes back to Claude. Any parsing problem fails closed for commands naming .env.
"""
import json
import re
import sys

ENV_TOKEN = re.compile(r"""(?:^|[\s/'"=<(])\.env(?:\.(?!example\b)[A-Za-z0-9_-]+)?(?=$|[\s'";|&)>])""")
P = r"""["']?[^|;&<>`$]*\.env["']?"""
ALLOWED = [
    re.compile(rf"""^\s*grep\s+-oE?\s+['"]\^\[A-Z(?:a-z)?0-9_\]\+['"]\s+{P}\s*(?:\|\s*sort\s*)?$"""),
    re.compile(rf"""^\s*grep\s+['"]\^[A-Z0-9_]+=['"]\s+{P}\s*>>\s*{P}\s*$"""),
    re.compile(rf"""^\s*cp\s+["']?[^|;&<>`$]*\.env\.example["']?\s+{P}\s*$"""),
    re.compile(r"""^\s*(?:ls(?:\s+-[a-zA-Z]+)*|test\s+-[ef]|\[\s+-[ef]|git\s+(?:status|check-ignore)(?:\s+-v)?)\s+[^|;&<>`$]*$"""),
]
MESSAGE = ("Blocked by the AIOS secret guard: this would show the contents of a .env file. Keys never enter the chat. "
           "Scripts in execution/ read .env themselves; to see which keys are set, run aios_status.py (names only).")


def names_env(path: str) -> bool:
    name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    if tool == "Bash":
        cmd = ti.get("command", "")
        if ENV_TOKEN.search(cmd) and not any(a.match(cmd) for a in ALLOWED):
            print(MESSAGE, file=sys.stderr)
            sys.exit(2)
        return
    for key in ("file_path", "path", "notebook_path"):
        if isinstance(ti.get(key), str) and names_env(ti[key]):
            print(MESSAGE, file=sys.stderr)
            sys.exit(2)
    if tool == "Grep" and isinstance(ti.get("glob"), str) and ".env" in ti["glob"] and "example" not in ti["glob"]:
        print(MESSAGE, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
