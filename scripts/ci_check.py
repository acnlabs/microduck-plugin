#!/usr/bin/env python3
"""GPU-free package checks. No third-party imports. Run from anywhere."""

from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\\.\\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
ALLOWED_PLUGIN = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def die(msg: str) -> None:
    print(f"ci_check: {msg}", file=sys.stderr)
    raise SystemExit(1)


def check_plugin_json() -> None:
    raw = json.loads((ROOT / "plugin.json").read_text())
    extra = set(raw) - ALLOWED_PLUGIN
    if extra:
        die(f"plugin.json unknown fields: {sorted(extra)}")
    if raw.get("$schema") != SCHEMA:
        die("plugin.json $schema must be Agent Plugins 1.0.0")
    name = raw.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 64) or not PLUGIN_NAME_RE.match(name):
        die(f"plugin.json invalid name: {name!r}")
    if name != "microduck-plugin":
        die(f"plugin.json name must be microduck-plugin, got {name!r}")
    if "keywords" in raw:
        kws = raw["keywords"]
        if not isinstance(kws, list) or not all(isinstance(k, str) for k in kws):
            die("plugin.json keywords must be an array of strings")
    if "author" in raw:
        author = raw["author"]
        if not isinstance(author, dict) or set(author) - {"name", "email", "url"}:
            die("plugin.json author must only have name/email/url")
    if "extensions" in raw and not isinstance(raw["extensions"], dict):
        die("plugin.json extensions must be an object")
    print("ci_check: plugin.json ok")


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        die("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        die("SKILL.md frontmatter is not closed")
    data: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal key, buf
        if key is None:
            return
        data[key] = "\n".join(buf).strip()
        key = None
        buf = []

    for line in parts[1].splitlines():
        if not line.strip():
            continue
        if line[0] not in " \t" and ":" in line:
            flush()
            left, right = line.split(":", 1)
            key = left.strip()
            buf = [right.strip().strip("\"'")]
        elif key is not None:
            buf.append(line.strip())
    flush()
    return data


def check_skills() -> None:
    skills = ROOT / "skills"
    found = False
    for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        found = True
        meta = _frontmatter(skill_md.read_text())
        name = meta.get("name", "")
        desc = meta.get("description", "")
        if name != skill_dir.name:
            die(f"{skill_md}: name {name!r} must match directory {skill_dir.name!r}")
        if not SKILL_NAME_RE.match(name) or len(name) > 64:
            die(f"{skill_md}: invalid name {name!r}")
        if not (1 <= len(desc) <= 1024):
            die(f"{skill_md}: description must be 1–1024 characters (got {len(desc)})")
        print(f"ci_check: {skill_md.relative_to(ROOT)} ok ({len(desc)}-char description)")
    if not found:
        die("no skills/*/SKILL.md found")


def check_scripts() -> None:
    scripts = sorted((ROOT / "skills/microduck-rl/scripts").glob("*"))
    sh = [p for p in scripts if p.suffix == ".sh"]
    if not sh:
        die("no shell scripts found")
    for path in sh:
        subprocess.run(["bash", "-n", str(path)], check=True)
        print(f"ci_check: bash -n {path.name} ok")
    gate = ROOT / "skills/microduck-rl/scripts/gate_check.py"
    py_compile.compile(str(gate), doraise=True)
    print("ci_check: gate_check.py compiles")


def main() -> int:
    check_plugin_json()
    check_skills()
    check_scripts()
    print("ci_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
