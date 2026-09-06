#!/usr/bin/env python3
"""GPU-free package checks. No third-party imports. Validates plugin.json
against the vendored Agent Plugins 1.0 schema in schemas/plugin.schema.json.
"""

from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SCHEMA_PATH = ROOT / "schemas/plugin.schema.json"
EXPECTED_PACKAGE_NAME = "microduck-plugin"


def die(msg: str) -> None:
    print(f"ci_check: {msg}", file=sys.stderr)
    raise SystemExit(1)


def check_plugin_json() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    raw = json.loads((ROOT / "plugin.json").read_text())

    if schema.get("additionalProperties") is False:
        extra = set(raw) - set(schema.get("properties", {}))
        if extra:
            die(f"plugin.json unknown fields vs {SCHEMA_PATH.name}: {sorted(extra)}")

    for field in schema.get("required", []):
        if field not in raw:
            die(f"plugin.json missing required field {field!r}")

    schema_const = schema["properties"]["$schema"]["const"]
    if raw.get("$schema") != schema_const:
        die(f"plugin.json $schema must be {schema_const}")

    name_spec = schema["properties"]["name"]
    name = raw.get("name")
    if not isinstance(name, str):
        die("plugin.json name must be a string")
    if not (name_spec["minLength"] <= len(name) <= name_spec["maxLength"]):
        die(f"plugin.json name length out of range: {name!r}")
    if not re.match(name_spec["pattern"], name):
        die(f"plugin.json name fails schema pattern: {name!r}")
    if name != EXPECTED_PACKAGE_NAME:
        die(f"plugin.json name must be {EXPECTED_PACKAGE_NAME}, got {name!r}")

    if "keywords" in raw:
        kws = raw["keywords"]
        if not isinstance(kws, list) or not all(isinstance(k, str) for k in kws):
            die("plugin.json keywords must be an array of strings")
    if "author" in raw:
        author = raw["author"]
        allowed = set(schema["properties"]["author"]["properties"])
        if not isinstance(author, dict) or set(author) - allowed:
            die(f"plugin.json author must only have {sorted(allowed)}")
        if author.get("name") != "acnlabs":
            die("plugin.json author.name must be acnlabs")
    if "extensions" in raw and not isinstance(raw["extensions"], dict):
        die("plugin.json extensions must be an object")

    print(f"ci_check: plugin.json ok (schema {SCHEMA_PATH.relative_to(ROOT)})")


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
        if name.endswith("-skill"):
            die(f"{skill_md}: do not suffix the skill id with -skill")
        if not SKILL_NAME_RE.match(name) or len(name) > 64:
            die(f"{skill_md}: invalid name {name!r}")
        if not (1 <= len(desc) <= 1024):
            die(f"{skill_md}: description must be 1–1024 characters (got {len(desc)})")
        if "author: acnlabs" not in skill_md.read_text():
            die(f"{skill_md}: metadata.author must be acnlabs")
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
    export = (ROOT / "skills/microduck-rl/scripts/export_publish.sh").read_text()
    if "rm -f output.onnx" in export:
        die("export_publish.sh must not delete the checkout's output.onnx")
    if "--onnx-file" not in export:
        die("export_publish.sh must pass --onnx-file to a dedicated path")


def main() -> int:
    if not SCHEMA_PATH.is_file():
        die(f"missing vendored schema: {SCHEMA_PATH}")
    check_plugin_json()
    check_skills()
    check_scripts()
    print("ci_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
