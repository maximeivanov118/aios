#!/usr/bin/env python3
"""
Library-wide lint for a skills folder.

quick_validate.py checks one skill in isolation. This checks the things that only
show up across the whole library: descriptions too thin or too long to trigger,
two skills competing for the same request, leftover template placeholders,
duplicates, name collisions with built-in skills, and mirror drift.

Usage:
    lint_library.py [--skills DIR] [--mirror DIR] [--budget N] [--json]

Exit code 1 if any FAIL, 0 otherwise (WARNs never fail the run).
"""

import argparse
import difflib
import filecmp
import json
import os
import re
import sys
from pathlib import Path

DESC_MIN = 150
DESC_MAX = 700
MIN_TRIGGERS = 3
SIMILARITY_MAX = 0.9
IGNORE = {"__pycache__", ".DS_Store", "node_modules"}

# Skills that ship with Claude Code or its bundled plugins. A personal skill with
# the same name shadows or fights the built-in one.
BUILTIN_NAMES = {
    "simplify", "init", "loop", "schedule", "run", "code-review", "security-review",
    "update-config", "keybindings-help", "claude-api", "dataviz",
    "fewer-permission-prompts", "plugin-authoring", "workflow-authoring",
    "artifact-design", "artifact-diagramming", "artifact-capabilities",
}

# Identity placeholders mean an imported skill was never personalised. Other
# {{TOKENS}} are often legitimate template variables, so they are not matched.
PLACEHOLDER_RE = re.compile(
    r"your-[a-z-]*email@example\.com|\byou@example\.com|\bYour Name\b|\bYOUR_NAME\b|"
    r"\{\{(USER_NAME|ACCOUNT|COMMUNITY_[A-Z]+)\}\}|Demo Library Skill"
)
WHEN_RE = re.compile(r"\b(use (this )?(skill )?when(ever)?|always use|must use)\b", re.I)
NOT_FOR_RE = re.compile(r"\bnot for\b", re.I)
QUOTED_RE = re.compile(r"[\"“]([^\"”]{3,80})[\"”]")
# A skill that hands back something a person reads or looks at should check it first.
OUTPUT_RE = re.compile(
    r"\b(write|draft|generate|create|produce|design|build)s?\b.*\b(email|post|proposal|"
    r"thumbnail|slide|infographic|diagram|report|copy|carousel|website|video)", re.I
)
VERIFY_RE = re.compile(r"^#{1,3}\s.*\bverif", re.I | re.M)
SCRIPT_EXT = {".py", ".js", ".sh", ".ts"}


def read_skill(folder):
    """Return a dict describing one skill folder, or None if it holds no skill file."""
    entries = {p.name: p for p in folder.iterdir()} if folder.is_dir() else {}
    skill_file = entries.get("SKILL.md")
    misnamed = None
    if skill_file is None:
        for name, p in entries.items():
            if name.lower() == "skill.md":
                skill_file, misnamed = p, name
    if skill_file is None:
        return None
    text = skill_file.read_text(errors="ignore")
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.S)
    fm = fm_match.group(1) if fm_match else ""
    d = re.search(r"^description:[ \t]*(.*(?:\n[ \t]+.*)*)", fm, re.M)
    desc = " ".join(d.group(1).split()) if d else ""
    desc = re.sub(r"^[>|][-+]?\s*", "", desc).strip()
    if len(desc) > 1 and desc[0] == "'" and desc[-1] == "'":
        desc = desc[1:-1].replace("''", "'")
    if len(desc) > 1 and desc[0] == '"' and desc[-1] == '"':
        desc = desc[1:-1]
    nm = re.search(r"^name:[ \t]*(.+)$", fm, re.M)
    return {
        "declared_name": nm.group(1).strip().strip("'\"") if nm else "",
        "name": folder.name,
        "path": folder,
        "text": text,
        "desc": desc,
        "misnamed": misnamed,
        "slash_only": bool(re.search(r"^disable-model-invocation:\s*true", fm, re.M)),
        "loose_scripts": sorted(
            n for n, p in entries.items() if p.is_file() and p.suffix in SCRIPT_EXT
        ),
    }


def load_library(root):
    root = Path(root).expanduser()
    skills = []
    for folder in sorted(root.iterdir()):
        if folder.name in IGNORE or folder.name.startswith("."):
            continue
        s = read_skill(folder)
        if s:
            skills.append(s)
    return skills


def triggers(desc):
    return {t.strip().lower() for t in QUOTED_RE.findall(desc)}


def words(name):
    return set(name.split("-"))


def has_neighbour(skill, skills):
    """A neighbour is another skill sharing a name word, e.g. gmail / gmail-label."""
    mine = words(skill["name"]) - {"skill", "agent", "agents", "create", "generator"}
    return any(
        o is not skill and mine & words(o["name"]) for o in skills
    )


def dir_differs(a, b):
    cmp = filecmp.dircmp(a, b, ignore=list(IGNORE))
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return True
    return any(dir_differs(Path(a) / d, Path(b) / d) for d in cmp.common_dirs)


def lint(skills, mirror=None, budget=None):
    """Return a list of (level, rule, skill_name, message)."""
    out = []

    def add(level, rule, name, msg):
        out.append((level, rule, name, msg))

    invocable = [s for s in skills if not s["slash_only"]]

    for s in skills:
        n, desc = s["name"], s["desc"]
        if s["misnamed"]:
            add("FAIL", "filename", n, f"skill file is '{s['misnamed']}', must be exactly SKILL.md")
        if s["declared_name"] != n:
            add("WARN" if s["slash_only"] else "FAIL", "name-mismatch", n,
                f"frontmatter name is '{s['declared_name']}', folder is '{n}'")
        if n in BUILTIN_NAMES:
            add("FAIL", "builtin-collision", n, "name collides with a built-in skill")
        if PLACEHOLDER_RE.search(s["text"]):
            hit = PLACEHOLDER_RE.search(s["text"]).group(0)
            # A slash-only skill is parked: never auto-triggered, so unpersonalised is a note, not a failure.
            add("WARN" if s["slash_only"] else "FAIL", "placeholder", n, f"template placeholder left in: {hit}")
        if s["loose_scripts"]:
            add("WARN", "loose-scripts", n, f"scripts in skill root, not scripts/: {', '.join(s['loose_scripts'])}")
        if OUTPUT_RE.search(desc) and not VERIFY_RE.search(s["text"]):
            add("WARN", "no-verify", n, "produces output for a reader but has no Verify section")
        if s["slash_only"]:
            continue  # description is never shown to the model; shape does not matter
        if not desc:
            add("FAIL", "desc-missing", n, "no description")
            continue
        if len(desc) < DESC_MIN:
            add("FAIL", "desc-thin", n, f"description is {len(desc)} chars, minimum {DESC_MIN}")
        if len(desc) > DESC_MAX:
            add("FAIL", "desc-long", n, f"description is {len(desc)} chars, maximum {DESC_MAX}")
        if not WHEN_RE.search(desc):
            add("FAIL", "desc-no-when", n, 'no forceful when-clause ("ALWAYS use when" / "Use when" / "MUST use")')
        if len(triggers(desc)) < MIN_TRIGGERS:
            add("FAIL", "desc-few-triggers", n, f"{len(triggers(desc))} quoted trigger phrases, minimum {MIN_TRIGGERS}")
        if has_neighbour(s, invocable) and not NOT_FOR_RE.search(desc):
            add("FAIL", "desc-no-not-for", n, 'has a neighbouring skill but no "Not for ..." clause')

    # Cross-skill rules
    for i, a in enumerate(skills):
        for b in skills[i + 1:]:
            pair = f"{a['name']} + {b['name']}"
            if a["desc"] and a["desc"] == b["desc"]:
                add("FAIL", "duplicate", pair, "identical descriptions")
            elif difflib.SequenceMatcher(None, a["text"], b["text"]).quick_ratio() > SIMILARITY_MAX and \
                    difflib.SequenceMatcher(None, a["text"], b["text"]).ratio() > SIMILARITY_MAX:
                add("FAIL", "duplicate", pair, f"SKILL.md more than {int(SIMILARITY_MAX * 100)}% similar")
            if a["slash_only"] or b["slash_only"]:
                continue
            shared = triggers(a["desc"]) & triggers(b["desc"])
            if shared:
                add("FAIL", "shared-trigger", pair, f"both claim: {', '.join(sorted(shared))}")

    total = sum(len(s["desc"]) for s in invocable)
    if budget:
        if total > budget:
            add("FAIL", "budget", "(library)", f"descriptions total {total} chars, over the {budget} budget")
    else:
        add("WARN", "budget", "(library)", f"descriptions total {total} chars across {len(invocable)} model-invocable skills; no --budget set")

    if mirror:
        mirror = Path(mirror).expanduser()
        by_name = {s["name"]: s for s in skills}
        if mirror.is_dir():
            for folder in sorted(mirror.iterdir()):
                if folder.name in by_name and folder.is_dir():
                    if dir_differs(by_name[folder.name]["path"], folder):
                        add("FAIL", "mirror-drift", folder.name, f"copy in {mirror} differs from the original")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skills", default=".claude/skills")
    ap.add_argument("--mirror", default=None, help="second skills folder that must match its originals")
    ap.add_argument("--budget", type=int, default=None, help="total description chars the listing can hold")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    skills = load_library(args.skills)
    findings = lint(skills, args.mirror, args.budget)
    fails = [f for f in findings if f[0] == "FAIL"]
    warns = [f for f in findings if f[0] == "WARN"]

    if args.json:
        print(json.dumps([dict(zip(("level", "rule", "skill", "message"), f)) for f in findings], indent=2))
    else:
        by_rule = {}
        for f in findings:
            by_rule.setdefault((f[0], f[1]), []).append(f)
        for (level, rule), items in sorted(by_rule.items()):
            print(f"\n{level} {rule} ({len(items)})")
            for _, _, name, msg in items:
                print(f"  {name}: {msg}")
        print(f"\n{len(skills)} skills · {len(fails)} FAIL · {len(warns)} WARN")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
