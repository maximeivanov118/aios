#!/usr/bin/env python3
"""Bring the shared AIOS up to date. The company's own part is never touched.

usage: python3 <skill>/scripts/aios_update.py [--root <aios folder>]            # update now
       python3 <skill>/scripts/aios_update.py --check                         # say whether an update waits, change nothing
       python3 <skill>/scripts/aios_update.py --remote <url or path>          # another source (a fork, a test copy)

A clone updates from its git origin; a zip install from the repository named in aios-source.json.

An AIOS folder from the AIOS repository has two parts (see CLAUDE.md):
  shared  every file git tracks: it came with the repository, and an update replaces it;
  own     everything else (context/, knowledge/, tasks/, projects/, own skills, .env, aios.json): git ignores it.
An update only moves the shared files forward (git fast-forward). Two things are first set aside, with their paths,
in .tmp/aios-update-<time>/:
  - a local edit to a shared file that the update changes (an edit to a file it does not change stays as it is);
  - an own file sitting exactly where the update adds a new shared file.
A folder installed from the zip has no .git: its first update makes it a clone of the version it came from
(.aios-version), without changing any file, and then updates it. git must be installed.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def find_root(argv: list) -> Path:
    if "--root" in argv:
        return Path(argv[argv.index("--root") + 1]).expanduser().resolve()
    p = Path.cwd().resolve()
    for d in (p, *p.parents):
        if (d / "aios-source.json").exists():
            return d
    sys.exit("This AIOS was not installed from the AIOS repository (no aios-source.json), so it gets no updates this way.")


def run(root: Path, *args: str) -> tuple:
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=180)
    return p.returncode, (p.stdout + p.stderr).strip()


def git(root: Path, *args: str) -> str:
    code, out = run(root, *args)
    if code != 0:
        sys.exit(f"git {' '.join(args)} failed. Nothing else was changed.\n{out}")
    return out


def names(text: str) -> set:
    return {l.strip() for l in text.splitlines() if l.strip()}


def fetch(root: Path, url: str, branch: str) -> None:
    code, out = run(root, "fetch", "-q", url, f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
    if code != 0:
        sys.exit(f"Could not reach the AIOS repository ({url}). Offline? Nothing was changed.\n{out}")


def adopt(root: Path, url: str, branch: str) -> str:
    """Zip install → git clone of the version it came from. The index moves; no file in the folder changes."""
    base = (root / ".aios-version").read_text().strip() if (root / ".aios-version").exists() else ""
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", url)
    fetch(root, url, branch)
    known = bool(base) and not base.startswith("$") and run(root, "cat-file", "-e", base + "^{commit}")[0] == 0
    git(root, "reset", "-q", base if known else f"origin/{branch}")
    git(root, "checkout", "-q", "--", ".aios-version")     # the zip's filled-in stamp, not an edit of the owner's
    git(root, "branch", "-q", "-M", branch)
    git(root, "branch", "-q", "-u", f"origin/{branch}")
    if known:
        return f"This folder came from the zip; it is now linked to the AIOS repository at version {base[:7]}."
    return ("This folder came from the zip and its version is unknown; it is now linked to the newest version, "
            "so any shared file that differs from it counts as a local edit.")


def main() -> None:
    argv = sys.argv[1:]
    if shutil.which("git") is None:
        sys.exit("git is not installed. On a Mac, run `xcode-select --install` in a terminal, then try again.")
    root = find_root(argv)
    src = json.loads((root / "aios-source.json").read_text())
    url = src["repo"]                                       # a zip install has only this
    if (root / ".git").exists():
        code, origin = run(root, "remote", "get-url", "origin")
        url = origin if code == 0 and origin else url       # a clone updates from where it was cloned, like `git pull`
    if "--remote" in argv:
        url = argv[argv.index("--remote") + 1]
    branch = src.get("branch", "main")
    target = f"origin/{branch}"

    note = ""
    if not (root / ".git").exists():
        if "--check" in argv:
            print("Installed from the zip. The first \"update the AIOS\" links this folder to the AIOS repository "
                  "(nothing of yours changes), then brings in the newest shared AIOS.")
            return
        note = adopt(root, url, branch)
        print(note)
    else:
        fetch(root, url, branch)

    behind = int(git(root, "rev-list", "--count", f"HEAD..{target}"))
    if behind == 0:
        print("The shared AIOS is up to date.")
        return
    log = git(root, "log", "--oneline", "--no-decorate", f"HEAD..{target}")
    if "--check" in argv:
        print(f"{behind} update(s) wait for the shared AIOS:\n{log}\nSay \"update the AIOS\" to bring them in. Your own part is never touched.")
        return
    if run(root, "merge-base", "--is-ancestor", "HEAD", target)[0] != 0:
        sys.exit("This folder has its own commits on the shared files, so it cannot simply move forward. "
                 "Nothing was changed. Run `git status` and `git log`, or ask whoever set it up.")

    old = git(root, "rev-parse", "--short", "HEAD")
    changed = names(git(root, "diff", "--name-only", "HEAD", target))
    added = names(git(root, "diff", "--name-only", "--diff-filter=A", "HEAD", target))
    edited = names(git(root, "diff", "--name-only", "HEAD"))
    clash_edit = sorted(edited & changed)
    clash_own = sorted(p for p in added if (root / p).is_file())
    aside = root / ".tmp" / f"aios-update-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    for rel in clash_edit + clash_own:
        if (root / rel).is_file():
            (aside / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, aside / rel)
    if clash_edit:
        git(root, "checkout", "-q", "HEAD", "--", *clash_edit)
    for rel in clash_own:
        (root / rel).unlink()
    git(root, "merge", "-q", "--ff-only", target)
    new = git(root, "rev-parse", "--short", "HEAD")

    print(f"Shared AIOS updated: {old} → {new}, {behind} change(s):\n{log}")
    print(f"{len(changed)} shared file(s) changed. Your own part was not touched.")
    if clash_edit:
        print(f"\nYour edits to these shared files were set aside in {aside.relative_to(root)}/ (the update replaced them):")
        print("\n".join(f"  {p}" for p in clash_edit))
    if clash_own:
        print(f"\nThese files of yours sat where the update adds a shared file; they are in {aside.relative_to(root)}/ now:")
        print("\n".join(f"  {p}" for p in clash_own))
    migrations = sorted(p for p in changed if p.startswith("data/supabase/migrations/"))
    if migrations:
        print("\nNew or changed migrations: run `python3 execution/apply_migrations.py`, then "
              "`python3 execution/security_check.py` (stage 2 rules):")
        print("\n".join(f"  {p}" for p in migrations))
    print("\nNext: /aios to see where you are.")


if __name__ == "__main__":
    main()
