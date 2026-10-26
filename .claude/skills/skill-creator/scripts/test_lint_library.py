#!/usr/bin/env python3
"""
Planted-fixture tests for lint_library.py: every rule must reject its bad input
and stay quiet on the good one. Run: python3 test_lint_library.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lint_library import lint, load_library  # noqa: E402

GOOD = (
    'Writes or roasts a cold email using the 4-part framework and returns the final copy. '
    'ALWAYS use when the request involves drafting or fixing outbound email copy. '
    'Triggers: "write a cold email", "roast this email", "why is nobody replying", /{name}.'
)


def make(root, name, desc=None, body="# Skill\n\nSteps.\n", fname="SKILL.md", extra_fm="", files=None):
    d = Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    desc = GOOD.replace("{name}", name) if desc is None else desc
    # Keep each fixture's triggers unique unless a test wants a clash
    desc = desc.replace("cold email", f"{name} mail").replace("roast this email", f"roast {name}").replace(
        "why is nobody replying", f"why {name} silent")
    (d / fname).write_text(f"---\nname: {name}\ndescription: {desc}\n{extra_fm}---\n\n{body}")
    for f, content in (files or {}).items():
        (d / f).write_text(content)
    return d


def rules(root, **kw):
    return {(lvl, rule) for lvl, rule, _, _ in lint(load_library(root), **kw)}


class LintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def fails(self, **kw):
        return {r for lvl, r in rules(self.root, **kw) if lvl == "FAIL"}

    def warns(self, **kw):
        return {r for lvl, r in rules(self.root, **kw) if lvl == "WARN"}

    def test_good_skill_is_clean(self):
        make(self.root, "alpha")
        self.assertEqual(self.fails(), set())

    def test_thin_description(self):
        make(self.root, "alpha", desc='Use when "a b c", "d e f", "g h i".')
        self.assertIn("desc-thin", self.fails())

    def test_long_description(self):
        make(self.root, "alpha", desc=GOOD + " padding" * 100)
        self.assertIn("desc-long", self.fails())

    def test_no_when_clause(self):
        make(self.root, "alpha", desc=GOOD.replace("ALWAYS use when", "Relevant if"))
        self.assertIn("desc-no-when", self.fails())

    def test_few_triggers(self):
        make(self.root, "alpha", desc=GOOD.replace('"write a cold email", "roast this email", ', ""))
        self.assertIn("desc-few-triggers", self.fails())

    def test_neighbour_needs_not_for(self):
        make(self.root, "mail-send")
        make(self.root, "mail-label")
        self.assertIn("desc-no-not-for", self.fails())

    def test_neighbour_with_not_for_passes(self):
        make(self.root, "mail-send", desc=GOOD + " Not for labelling (use mail-label).")
        make(self.root, "mail-label", desc=GOOD + " Not for sending (use mail-send).")
        self.assertNotIn("desc-no-not-for", self.fails())

    def test_shared_trigger(self):
        clash = ' Also "book a meeting now".'
        make(self.root, "alpha", desc=GOOD + clash)
        make(self.root, "beta", desc=GOOD + clash)
        self.assertIn("shared-trigger", self.fails())

    def test_placeholder(self):
        make(self.root, "alpha", body="Send from your-email@example.com as {{USER_NAME}}.\n")
        self.assertIn("placeholder", self.fails())

    def test_placeholder_is_only_a_warning_when_slash_only(self):
        make(self.root, "alpha", body="Reply as {{USER_NAME}}.\n", extra_fm="disable-model-invocation: true\n")
        self.assertNotIn("placeholder", self.fails())
        self.assertIn("placeholder", self.warns())

    def test_template_variables_are_not_placeholders(self):
        make(self.root, "alpha", body="Open http://localhost:{{PORT}} for {{PROJECT_NAME}}.\n")
        self.assertNotIn("placeholder", self.fails())

    def test_duplicate_body(self):
        body = "# Skill\n\n" + "A long shared procedure line.\n" * 40
        make(self.root, "alpha", body=body)
        make(self.root, "beta", body=body)
        self.assertIn("duplicate", self.fails())

    def test_distinct_bodies_not_duplicate(self):
        make(self.root, "alpha", body="# A\n\n" + "Scrape the map listing.\n" * 30)
        make(self.root, "beta", body="# B\n\n" + "Render every slide to an image.\n" * 30)
        self.assertNotIn("duplicate", self.fails())

    def test_builtin_collision(self):
        make(self.root, "simplify")
        self.assertIn("builtin-collision", self.fails())

    def test_name_mismatch(self):
        d = make(self.root, "alpha")
        f = d / "SKILL.md"
        f.write_text(f.read_text().replace("name: alpha", "name: beta"))
        self.assertIn("name-mismatch", self.fails())

    def test_misnamed_file(self):
        make(self.root, "alpha", fname="skill.md")
        self.assertIn("filename", self.fails())

    def test_budget(self):
        make(self.root, "alpha")
        self.assertIn("budget", self.fails(budget=100))
        self.assertNotIn("budget", self.fails(budget=100000))

    def test_slash_only_skips_description_rules(self):
        make(self.root, "alpha", desc="Short.", extra_fm="disable-model-invocation: true\n")
        self.assertEqual(self.fails(), set())

    def test_mirror_drift(self):
        make(self.root, "alpha")
        with tempfile.TemporaryDirectory() as mirror:
            make(mirror, "alpha")
            self.assertNotIn("mirror-drift", self.fails(mirror=mirror))
            (Path(mirror) / "alpha" / "SKILL.md").write_text("changed")
            self.assertIn("mirror-drift", self.fails(mirror=mirror))

    def test_warn_loose_scripts(self):
        make(self.root, "alpha", files={"run.py": "print(1)\n"})
        self.assertIn("loose-scripts", self.warns())

    def test_warn_no_verify(self):
        make(self.root, "alpha", desc=GOOD)  # "Writes ... email" → output-producing
        self.assertIn("no-verify", self.warns())
        make(self.root, "alpha", body="# Skill\n\n## Verify before returning\n\nCheck it.\n")
        self.assertNotIn("no-verify", self.warns())


if __name__ == "__main__":
    unittest.main(verbosity=1)
