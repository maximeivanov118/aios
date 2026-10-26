#!/usr/bin/env python3
"""Where is this AIOS, and what is the next step? Every answer comes from a check, never from memory.

usage: python3 <skill>/scripts/aios_status.py [--root <aios folder>]          # table + the one next step
       python3 <skill>/scripts/aios_status.py --brief | --json
       python3 <skill>/scripts/aios_status.py record data                     # runs the migration check + security gate
       python3 <skill>/scripts/aios_status.py record knowledge --query "refund policy"   # store count + a search that must hit
       python3 <skill>/scripts/aios_status.py record mcp --count 12           # the document count Claude read THROUGH the MCP
       python3 <skill>/scripts/aios_status.py record connect --name gmail --kind mail --how "claude.ai connector" \
               --evidence "listed the 3 latest subjects on 2026-11-02"
       python3 <skill>/scripts/aios_status.py record manual --evidence "2 weeks of daily use, 14 log rows"
       python3 <skill>/scripts/aios_status.py record tools --evidence "builder delivered: invoice chaser, lead brief"
       python3 <skill>/scripts/aios_status.py record dashboard --evidence "https://acme-aios.vercel.app"
       python3 <skill>/scripts/aios_status.py mcp                             # writes .mcp.json (Supabase MCP, read-only)

--root defaults to the nearest folder above the current one that holds aios.json.
"record" refuses when the stage's checks do not pass. Two kinds of stage:
  PROVEN   (0 start, 1 context, 2 data, 3 knowledge, and the store read of 4): a script checks the real thing.
  ATTESTED (the work-tool connections of 4, and 5, 6, 7): no script can see a claude.ai connector, a week of work
           or a delivered app, so the owner's evidence is recorded as given, after the checks that do exist.
The table says which is which, so nobody mistakes an attested stage for a proven one.
Editions (aios.json → edition): "client" (the default) has 8 stages, the builder delivers 6 and 7. "solo" has no
builder: stage 6 is the owner's first own skill, and there is no stage 7.
Secrets: .env is read only for key NAMES and the project ref; no value is ever printed.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STAGES = [
    ("start", "Start", "the folder, the rules and the state file", "proven"),
    ("context", "Context", "who the company is, how it works, what it wants", "proven"),
    ("data", "Data store", "a private Supabase store that passes the security gate", "proven"),
    ("knowledge", "Knowledge", "company documents in the store, findable by search", "proven"),
    ("connect", "Connect tools", "Claude can read the store and at least one work tool", "partly attested"),
    ("manual", "Use it by hand", "two weeks of real tasks done with Claude, logged", "attested"),
    ("tools", "Skills and tools", "the first own skill, and the builder's tools delivered", "attested"),
    ("dashboard", "Dashboard", "the mission-control app, delivered by the builder", "attested"),
]
SOLO_TOOLS = ("tools", "First own skill", "the task done most often, turned into a skill", "partly attested")
REQUIRED_KEYS = ("SUPABASE_URL", "SUPABASE_PROJECT_REF", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_ACCESS_TOKEN")
CONTEXT_FILES = ("business-info.md", "personal-info.md", "strategy.md", "current-data.md")
MIN_WORDS = 60


def find_root(argv: list[str]) -> Path:
    if "--root" in argv:
        return Path(argv[argv.index("--root") + 1]).expanduser().resolve()
    p = Path.cwd().resolve()
    for d in (p, *p.parents):
        if (d / "aios.json").exists():
            return d
    sys.exit("no aios.json here or above. Start a new AIOS with /aios (stage 0), or pass --root <folder>.")


def solo(st: dict) -> bool:
    return st.get("edition") == "solo"


def stages(st: dict) -> list:
    return STAGES[:6] + [SOLO_TOOLS] if solo(st) else STAGES


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def env_names(root: Path) -> dict:
    """KEY -> True when it has a non-empty value. Values never leave this function."""
    f = root / ".env"
    out = {}
    if f.exists():
        for line in f.read_text().splitlines():
            m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", line)
            if m:
                out[m.group(1)] = bool(m.group(2).strip().strip('"').strip("'"))
    return out


def project_ref(root: Path) -> str:
    for line in (root / ".env").read_text().splitlines():
        m = re.match(r"^\s*SUPABASE_PROJECT_REF\s*=\s*['\"]?([a-z0-9]+)", line)
        if m:
            return m.group(1)
    return ""


def words(text: str) -> int:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(("#", ">", "|---")))
    return len(re.findall(r"[A-Za-zÀ-ÿ0-9]{2,}", text))


def first_table(path: Path) -> list[list[str]]:
    """Body rows (cells) of the FIRST Markdown table in a file: header and separator dropped, later tables ignored."""
    if not path.exists():
        return []
    rows, started = [], False
    for line in path.read_text().splitlines():
        if line.strip().startswith("|"):
            started = True
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif started:
            break
    return [r for r in rows[2:] if "FILL" not in " ".join(r) and sum(1 for c in r if c) >= 2]


def table_rows(path: Path) -> int:
    return len(first_table(path))


def log_quality(path: Path) -> tuple:
    """(valid rows, distinct dates, days spanned). Valid = a real date + numeric minutes with and without Claude."""
    valid, dates = 0, set()
    for r in first_table(path):
        if len(r) < 4:
            continue
        try:
            d = datetime.strptime(r[0], "%Y-%m-%d").date()
            float(r[2]); float(r[3])
        except ValueError:
            continue
        valid += 1
        dates.add(d)
    span = (max(dates) - min(dates)).days if dates else 0
    return valid, len(dates), span


def custom_skills(root: Path) -> list[str]:
    d = root / ".claude" / "skills"
    kit = set((d / ".kit-manifest").read_text().split()) if (d / ".kit-manifest").exists() else set()
    return sorted(p.name for p in d.iterdir() if p.is_dir() and (p / "SKILL.md").exists() and p.name not in kit) if d.exists() else []


def checks(root: Path, st: dict) -> dict:
    """stage id -> list of (ok, what to do when not ok)."""
    rec = st.get("stages", {})
    env = env_names(root)
    gi = (root / ".gitignore").read_text() if (root / ".gitignore").exists() else ""
    c = {}
    c["start"] = [
        ((root / "CLAUDE.md").exists(), "CLAUDE.md is missing: run stage 0 again (aios_init.py), it only adds missing files."),
        (bool(re.search(r"^\.env$", gi, re.M)), ".gitignore must hold a line '.env' so keys never reach git."),
    ]
    ctx = []
    for name in CONTEXT_FILES:
        f = root / "context" / name
        if not f.exists():
            ctx.append((False, f"context/{name} is missing."))
            continue
        t = f.read_text()
        left = t.count("<!-- FILL")
        n = words(t)
        ctx.append((left == 0 and n >= MIN_WORDS,
                    f"context/{name}: {left} section(s) still to fill, {n} words written (need {MIN_WORDS}+). "
                    f"Run the context interview for this file (references/stage-1-context.md)."))
    c["context"] = ctx
    missing = [k for k in REQUIRED_KEYS if not env.get(k)]
    c["data"] = [
        ((root / ".env").exists(), "no .env yet: copy .env.example to .env, then fill it from the Supabase dashboard (references/stage-2-data.md)."),
        (not missing, f".env still needs: {', '.join(missing)} (names only; the owner pastes the values into the file, never into the chat)."),
        (bool(rec.get("data")), "store not proven yet: run apply_migrations.py, the dashboard steps, backup_db.py, then `aios_status.py record data`."),
    ]
    kfiles = [p for p in (root / "knowledge").rglob("*") if p.is_file() and p.name not in ("README.md", ".gitkeep", ".DS_Store")] if (root / "knowledge").exists() else []
    c["knowledge"] = [
        (bool(kfiles), "knowledge/ is empty: collect the company documents there first (references/stage-3-knowledge.md)."),
        (bool(rec.get("knowledge")), "documents not proven in the store: /knowledge-ingest knowledge/<folder>, then `aios_status.py record knowledge --query \"<a phrase from one document>\"`."),
    ]
    mcp = (root / ".mcp.json").read_text() if (root / ".mcp.json").exists() else ""
    conns = [x for x in st.get("connections", []) if x.get("evidence")]
    c["connect"] = [
        ("mcp.supabase.com" in mcp, "Claude cannot read the store yet: run `aios_status.py mcp`, restart Claude Code, then /mcp to sign in to Supabase."),
        (bool(st.get("mcp_verified_at")), "prove Claude reads the store: ask the Supabase MCP for the row count of public.documents, then `aios_status.py record mcp --count <that number>`."),
        (bool(conns), "no work tool connected yet: connect one (mail, calendar, drive, CRM), read something real with it, then `aios_status.py record connect ...`."),
    ]
    audit = table_rows(root / "tasks" / "task-audit.md")
    log, days, span = log_quality(root / "tasks" / "repeats.md")
    c["manual"] = [
        (audit >= 5, f"tasks/task-audit.md has {audit} task(s) (need 5+): list the weekly tasks with time spent (references/stage-5-manual.md)."),
        (log >= 10 and days >= 5 and span >= 7,
         f"tasks/repeats.md: {log} valid log row(s) on {days} day(s) over {span} day(s) (need 10+ rows, 5+ days, 7+ days apart; "
         f"a valid row has a YYYY-MM-DD date and both minute columns as numbers)."),
        (bool(rec.get("manual")), "when the log feels honest, `aios_status.py record manual --evidence \"...\"`."),
    ]
    if solo(st):                                  # no builder: stage 6 ends at the first own skill, no stage 7
        c["tools"] = [
            (bool(custom_skills(root)), "no own skill yet: turn the task logged most often into a skill with /skill-creator (references/stage-6-tools.md)."),
            (bool(rec.get("tools")), "when the skill has done one real task: `aios_status.py record tools --evidence \"...\"`."),
        ]
        return c
    brief = root / "active" / "handover" / "tools-brief.md"
    c["tools"] = [
        (bool(custom_skills(root)), "no own skill yet: turn the task logged most often into a skill with /skill-creator."),
        (brief.exists() and "<!-- FILL" not in brief.read_text(), "write active/handover/tools-brief.md for the builder (references/stage-6-tools.md)."),
        (bool(rec.get("tools")), "when the builder has delivered the tools: `aios_status.py record tools --evidence \"...\"`."),
    ]
    dbrief = root / "active" / "handover" / "dashboard-brief.md"
    c["dashboard"] = [
        (dbrief.exists() and "<!-- FILL" not in dbrief.read_text(), "write active/handover/dashboard-brief.md for the builder (references/stage-7-dashboard.md)."),
        (bool(rec.get("dashboard")), "when the dashboard is live: `aios_status.py record dashboard --evidence \"<its URL>\"`."),
    ]
    return c


def summary(root: Path, st: dict) -> dict:
    c = checks(root, st)
    out, nxt = [], None
    for sid, name, goal, kind in stages(st):
        done = all(ok for ok, _ in c[sid])
        todo = [msg for ok, msg in c[sid] if not ok]
        if not done and nxt is None:
            nxt = {"stage": sid, "name": name, "step": todo[0], "open": todo}
        out.append({"stage": sid, "name": name, "goal": goal, "proof": kind, "done": done, "open": todo})
    skipped = [s["name"] for i, s in enumerate(out) if s["done"] and any(not o["done"] for o in out[:i])]
    return {"root": str(root), "company": st.get("company"), "stages": out, "next": nxt, "ahead_of_order": skipped,
            "builder": st.get("builder", {})}


def show(s: dict, brief: bool) -> None:
    n = s["next"]
    if brief:
        done = sum(x["done"] for x in s["stages"])
        print(f"AIOS {s['company']}: {done}/{len(s['stages'])} stages done.")
        print(f"Next: stage {[x['stage'] for x in s['stages']].index(n['stage'])} {n['name']} - {n['step']}" if n else "All stages done.")
        return
    print(f"AIOS of {s['company']}  ({s['root']})\n")
    for i, x in enumerate(s["stages"]):
        mark = "done" if x["done"] else ("NEXT" if n and x["stage"] == n["stage"] else "    ")
        print(f"  [{mark}] {i} {x['name']:<17} {x['goal']:<58} ({x['proof']})")
    if s["ahead_of_order"]:
        print(f"\n  note: {', '.join(s['ahead_of_order'])} passed before an earlier stage. Layers, not leaps: finish the earlier one.")
    if n:
        print(f"\nNext step (stage {n['name']}): {n['step']}")
        for o in n["open"][1:]:
            print(f"  then: {o}")
    else:
        print("\nEvery stage is done. Keep it alive: /prime at session start, new repeats become skills.")


def run(root: Path, *cmd: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, *cmd], cwd=root, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def record(root: Path, st: dict, argv: list[str]) -> None:
    def opt(name):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None
    stage = argv[argv.index("record") + 1]
    evidence = opt("--evidence")
    c = checks(root, st)
    if stage == "data":
        pre = [m for ok, m in c["data"][:2] if not ok]
        if pre:
            sys.exit("not recorded: " + " ".join(pre))
        code, out = run(root, "execution/apply_migrations.py", "--check")
        if code != 0:
            sys.exit("not recorded: migrations are not all applied.\n" + out)
        code, out = run(root, "execution/security_check.py")
        print(out)
        if code != 0:
            sys.exit("not recorded: the security gate failed. Fix each FAIL (directives/supabase_security_baseline.md), then run this again.")
        evidence = out.splitlines()[-1]
    elif stage == "knowledge":
        q = opt("--query")
        if not q:
            sys.exit("not recorded: give --query \"<a phrase that appears in one of the documents>\"")
        code, listing = run(root, "execution/ingest_folder.py", "--list")
        if code != 0 or "store is empty" in listing:
            sys.exit("not recorded: no document is in the store yet.\n" + listing)
        code, hits = run(root, "execution/search_store.py", q)
        print(hits)
        if code != 0:
            sys.exit(f"not recorded: searching for {q!r} found nothing. Search for a phrase that is really in a document.")
        n = sum(int(l.split()[0]) for l in listing.splitlines() if l.strip()[:1].isdigit())
        evidence = f"{n} documents in the store; search {q!r} -> {hits.splitlines()[0][:120]}"
    elif stage == "mcp":
        n = opt("--count")
        if n is None or not n.isdigit():
            sys.exit("not recorded: give --count <the number of rows in public.documents, as the Supabase MCP returned it>")
        code, listing = run(root, "execution/ingest_folder.py", "--list")
        if code != 0:
            sys.exit("not recorded: the store could not be read by the script either.\n" + listing)
        real = sum(int(l.split()[0]) for l in listing.splitlines() if l.strip()[:1].isdigit())
        if int(n) != real:
            sys.exit(f"not recorded: the MCP answer ({n}) does not match the store ({real}). Ask the MCP again, after /mcp sign-in.")
        st["mcp_verified_at"] = now()
        (root / "aios.json").write_text(json.dumps(st, indent=2) + "\n")
        print(f"Supabase MCP read verified: {real} documents")
        return
    elif stage == "connect":
        name, kind, how = opt("--name"), opt("--kind"), opt("--how")
        if not (name and kind and how and evidence):
            sys.exit("not recorded: give --name, --kind, --how and --evidence (what real thing was read through it, and when)")
        st["connections"] = [x for x in st.get("connections", []) if x.get("name") != name] + \
            [{"name": name, "kind": kind, "how": how, "evidence": evidence, "verified_at": now()}]
        (root / "aios.json").write_text(json.dumps(st, indent=2) + "\n")
        print(f"connection {name} recorded")
        c = checks(root, st)
        if not all(ok for ok, _ in c["connect"]):
            print("stage Connect tools not complete yet: " + " ".join(m for ok, m in c["connect"] if not ok))
            return
        evidence = ", ".join(x["name"] for x in st["connections"])
    elif stage in ("manual", "tools", "dashboard"):
        if stage not in c:
            sys.exit(f"not recorded: this AIOS has no {stage} stage (solo edition: it ends at stage 6, the first own skill).")
        if not evidence:
            sys.exit("not recorded: give --evidence \"...\"")
        pre = [m for ok, m in c[stage][:-1] if not ok]
        if pre:
            sys.exit("not recorded: " + " ".join(pre))
        if stage == "dashboard":
            st.setdefault("apps", {})["dashboard_url"] = evidence
    else:
        sys.exit(f"unknown stage {stage!r}: data, knowledge, mcp, connect, manual, tools, dashboard")
    st.setdefault("stages", {})[stage] = {"done_at": now(), "evidence": evidence}
    (root / "aios.json").write_text(json.dumps(st, indent=2) + "\n")
    print(f"stage {stage} recorded: {evidence}")


def write_mcp(root: Path) -> None:
    if not env_names(root).get("SUPABASE_PROJECT_REF"):
        sys.exit("SUPABASE_PROJECT_REF is not in .env yet (stage 2).")
    ref = project_ref(root)
    path = root / ".mcp.json"
    cfg = json.loads(path.read_text()) if path.exists() else {}
    cfg.setdefault("mcpServers", {})["supabase"] = {
        "type": "http",
        "url": f"https://mcp.supabase.com/mcp?project_ref={ref}&read_only=true&features=database,docs",
    }
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"wrote {path} (Supabase MCP, read-only, this project only). Restart Claude Code, then run /mcp and sign in to Supabase.")


def main() -> None:
    argv = sys.argv[1:]
    root = find_root(argv)
    st = json.loads((root / "aios.json").read_text())
    if "record" in argv:
        return record(root, st, argv)
    if "mcp" in argv:
        return write_mcp(root)
    s = summary(root, st)
    if "--json" in argv:
        print(json.dumps(s, indent=2))
    else:
        show(s, "--brief" in argv)


if __name__ == "__main__":
    main()
