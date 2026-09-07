#!/usr/bin/env python3
"""Validate and pack control.sh --record JSONL. No MuJoCo. Not train.sh."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT = {"obs": 61, "action": 14, "command": 13, "xyz": 3}


def die(msg: str) -> None:
    print(f"microduck-skill: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _vec(row: dict[str, Any], key: str, n: int) -> list[float]:
    raw = row.get(key)
    if not isinstance(raw, list) or len(raw) != n:
        raise ValueError(f"{key} must be length {n}")
    return [float(v) for v in raw]


def read_episode(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        die(f"not a file: {path}")
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"{path}:{i} invalid json ({exc})")
        if not isinstance(row, dict):
            die(f"{path}:{i} json object required")
        try:
            _vec(row, "obs", CONTRACT["obs"])
            _vec(row, "action", CONTRACT["action"])
            _vec(row, "command", CONTRACT["command"])
            _vec(row, "xyz", CONTRACT["xyz"])
        except (TypeError, ValueError) as exc:
            die(f"{path}:{i} {exc}")
        rows.append(row)
    if not rows:
        die(f"{path} has no steps")
    return rows


def episode_paths(src: Path) -> list[Path]:
    if src.is_dir():
        manifest = src / "manifest.json"
        if manifest.is_file():
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            files = [src / e["file"] for e in meta.get("episodes", [])]
            if files:
                return files
        found = sorted(src.glob("*.jsonl")) + sorted((src / "episodes").glob("*.jsonl"))
        if not found:
            die(f"no jsonl in {src}")
        return found
    return [src]


def cmd_check(paths: list[Path]) -> int:
    total = 0
    for src in paths:
        for path in episode_paths(src):
            rows = read_episode(path)
            skills = sorted({str(r.get("skill", "walking")) for r in rows})
            print(f"microduck-skill: check ok {path} steps={len(rows)} skills={skills}")
            total += len(rows)
    print(f"microduck-skill: check ok contract 61/14/13 steps={total}")
    return 0


def cmd_pack(paths: list[Path], out: Path) -> int:
    if out.exists() and any(out.iterdir()):
        die(f"--out is not empty: {out}")
    episodes_dir = out / "episodes"
    episodes_dir.mkdir(parents=True)
    catalog: list[dict[str, Any]] = []
    total = 0
    idx = 0
    for src in paths:
        for path in episode_paths(src):
            rows = read_episode(path)
            dest = episodes_dir / f"{idx:03d}.jsonl"
            shutil.copyfile(path, dest)
            skills = sorted({str(r.get("skill", "walking")) for r in rows})
            catalog.append(
                {
                    "file": f"episodes/{idx:03d}.jsonl",
                    "source": str(path.resolve()),
                    "steps": len(rows),
                    "skills": skills,
                }
            )
            print(f"microduck-skill: pack {path} -> {dest} steps={len(rows)}")
            total += len(rows)
            idx += 1
    manifest = {
        "contract": CONTRACT,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "steps": total,
        "episodes": catalog,
        "note": "Agent control datacollect. Not consumed by train.sh yet.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"microduck-skill: packed {idx} episodes / {total} steps -> {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check/pack Microduck control recordings")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="Validate JSONL or a packed directory")
    check.add_argument("paths", nargs="+", type=Path)
    pack = sub.add_parser("pack", help="Copy valid episodes into --out with a manifest")
    pack.add_argument("paths", nargs="+", type=Path)
    pack.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.cmd == "check":
        return cmd_check(args.paths)
    return cmd_pack(args.paths, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
