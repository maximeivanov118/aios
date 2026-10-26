#!/usr/bin/env python3
"""Stage 0 of /aios: turn a folder into an AIOS. Copies the template, never overwrites a file.

usage: python3 <skill>/scripts/aios_init.py --company "Acme BV" --owner "Jane Doe" [--target <folder>]

--target defaults to the current folder. Refuses the home folder, the file-system root, and a folder that is
already an AIOS (it has aios.json). Also copies the companion kit skills (setup, knowledge-ingest, prime, ...)
into <target>/.claude/skills/ when they are missing, so the folder works on its own and can be handed over.
Prints what it created and what it skipped. Writes nothing outside <target>.
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent            # .../skills/aios (resolved through any link)
# Started from the kit SOURCE (the builder's library links to it): use the BUILT kit instead, so the client folder
# gets the shared skills too and the client copy of every skill (model-invocable, generic text).
if (SKILL.parent.parent / "build_kit.py").exists():
    BUILT = SKILL.parent.parent / "dist.nosync" / "aios-kit"
    if not (BUILT / ".claude" / "skills" / "aios" / "SKILL.md").exists():
        sys.exit(f"this is the kit source. Build the kit first: python3 \"{SKILL.parent.parent / 'build_kit.py'}\"")
    SKILL = BUILT / ".claude" / "skills" / "aios"
TEMPLATE = SKILL / "template"
EDITION = "solo"          # build_kit.py --edition solo rewrites this line on the built copy: no builder, ends at stage 6
TEXT = {".md", ".json", ".example", ".txt", ".gitignore", ".toml", ".yaml", ".yml"}


def builder() -> dict:
    for p in (SKILL / "builder.json", SKILL.parent.parent / "builder.json"):
        if p.exists():
            return json.loads(p.read_text())
    return {"name": "your AIOS builder", "contact": "ask the person who gave you this kit"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--target", default=".")
    a = ap.parse_args()
    target = Path(a.target).expanduser().resolve()
    if target in (Path.home().resolve(), Path("/")):
        sys.exit(f"refused: {target} is too wide. Make a new folder for the AIOS (for example ~/Acme AIOS) and run there.")
    if (target / "aios.json").exists():
        sys.exit(f"{target} is already an AIOS. Run: python3 \"{SKILL}/scripts/aios_status.py\"")
    target.mkdir(parents=True, exist_ok=True)

    b = builder()
    subs = {"{{COMPANY}}": a.company, "{{OWNER}}": a.owner, "{{DATE}}": date.today().isoformat(),
            "{{BUILDER_NAME}}": b.get("name", ""), "{{BUILDER_CONTACT}}": b.get("contact", "")}
    created, skipped = [], []
    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        if any(part in ("__pycache__",) for part in rel.parts) or src.name == ".DS_Store":
            continue
        dst = target / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if dst.exists():
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in TEXT or src.name in TEXT:
            text = src.read_text(encoding="utf-8")
            for k, v in subs.items():
                text = text.replace(k, v)
            dst.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(src, dst)
        created.append(str(rel))

    # companion skills: every sibling of this skill, so the folder is self-contained
    skills_dir = target / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in SKILL.parent.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
    for name in names:
        dst = skills_dir / name
        if dst.resolve() == (SKILL.parent / name).resolve() or dst.exists():
            continue
        shutil.copytree(SKILL.parent / name, dst, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "builder.json"))
        created.append(f".claude/skills/{name}/")
    if not (skills_dir / ".kit-manifest").exists():      # the repository ships its own, and an update keeps it current
        (skills_dir / ".kit-manifest").write_text("\n".join(names) + "\n")
    for doc in ("README-START-HERE.md", "SHARED-SKILLS.md"):            # the kit's root docs, when started from a built kit
        src_doc = SKILL.parent.parent.parent / doc
        if src_doc.exists() and not (target / doc).exists():
            shutil.copy2(src_doc, target / doc)
            created.append(doc)

    state = {
        "aios_version": 1, "edition": EDITION, "company": a.company, "owner": a.owner, "created": date.today().isoformat(),
        "builder": b,
        "never_ingest": ["private", "active/handover"],
        "stages": {},
        "connections": [],
        "apps": {},
    }
    if EDITION == "solo":                      # no builder, so no handover briefs either
        del state["builder"]
        state["never_ingest"] = ["private"]
    (target / "aios.json").write_text(json.dumps(state, indent=2) + "\n")
    created.append("aios.json")
    print(f"AIOS created for {a.company} in {target}")
    print(f"created {len(created)}: " + ", ".join(created[:40]) + (" ..." if len(created) > 40 else ""))
    if skipped:
        print(f"kept as they were ({len(skipped)}): " + ", ".join(skipped))
    print("next: python3 \"%s/scripts/aios_status.py\" --root \"%s\"" % (SKILL, target))


if __name__ == "__main__":
    main()
