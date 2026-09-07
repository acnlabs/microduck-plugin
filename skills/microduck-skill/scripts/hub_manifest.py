#!/usr/bin/env python3
"""Hub manifest.json: command meaning, twist caps, deploy hint. Not a store."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

WALK_TWIST_CAPS = {"x": 0.3, "y": 0.2, "yaw": 1.5}
UNIT_TWIST_CAPS = {"x": 1.0, "y": 1.0, "yaw": 1.0}
WALK_COMMAND_NOTES = {
    "twist": "trained walk velocity (x m/s, y m/s, yaw rad/s)",
    "head": "trained",
    "body": "untrained_slot",
}
VEL_TOKENS = ("m/s", "rad/s", "vel", "velocity", "yaw rate")
REMAP_TOKENS = ("flag", "side:", "unused", "not encoded")
SIM_ONLY_TOKENS = (
    "never tested on hardware",
    "never run on hardware",
    "sim-only",
    "sim only",
    "sim_only",
)


def load_manifest(path: Path | str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    dest = Path(path)
    if not dest.is_file():
        return None
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"microduck-skill: ignore bad manifest {dest}: {exc}", file=sys.stderr)
        return None
    return data if isinstance(data, dict) else None


def _has_token(text: str, tokens: tuple[str, ...]) -> bool:
    blob = text.lower()
    return any(token in blob for token in tokens)


def _command_blob(manifest: dict[str, Any]) -> str:
    parts: list[str] = [str(manifest.get("description") or "")]
    command = manifest.get("command")
    if isinstance(command, dict):
        parts.append(json.dumps(command, ensure_ascii=False))
    return " ".join(parts)


def twist_is_velocity(manifest: dict[str, Any] | None) -> bool:
    """Walk speed caps only when this policy still talks like velocity."""
    if not manifest:
        return True
    command = manifest.get("command") if isinstance(manifest.get("command"), dict) else {}
    twist = command.get("twist") if command else None
    if isinstance(twist, list) and twist:
        slot_text = " ".join(str(item) for item in twist)
        if _has_token(slot_text, VEL_TOKENS):
            return True
        return False
    blob = _command_blob(manifest)
    if _has_token(blob, VEL_TOKENS) and not _has_token(blob, REMAP_TOKENS):
        return True
    if _has_token(blob, REMAP_TOKENS):
        return False
    if command:
        return False
    return True


def twist_caps(manifest: dict[str, Any] | None) -> dict[str, float]:
    return dict(WALK_TWIST_CAPS if twist_is_velocity(manifest) else UNIT_TWIST_CAPS)


def command_notes(manifest: dict[str, Any] | None) -> dict[str, Any]:
    if not manifest:
        return dict(WALK_COMMAND_NOTES)
    command = manifest.get("command") if isinstance(manifest.get("command"), dict) else {}
    twist = command.get("twist")
    return {
        "source": "manifest",
        "name": manifest.get("name"),
        "kind": manifest.get("kind"),
        "description": manifest.get("description"),
        "twist": twist if twist is not None else command.get("layout"),
        "head": command.get("head"),
        "body": command.get("body"),
        "idle": command.get("idle"),
        "caps": twist_caps(manifest),
    }


def is_episodic(manifest: dict[str, Any] | None) -> bool:
    return bool(manifest) and str(manifest.get("kind") or "").lower() == "episodic"


def is_behavior_extra(manifest: dict[str, Any] | None) -> bool:
    """Hub extras with kind=perpetual stay off the short-swap list."""
    if not manifest:
        return True
    kind = str(manifest.get("kind") or "").lower()
    if not kind:
        return True
    return kind == "episodic"


def behavior_duration_s(manifest: dict[str, Any] | None, default: float = 3.0) -> float:
    if not manifest:
        return default
    raw = manifest.get("duration_s")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    return value


def is_sim_only(manifest: dict[str, Any] | None) -> bool:
    if not manifest:
        return False
    eval_block = manifest.get("eval") if isinstance(manifest.get("eval"), dict) else {}
    blob = " ".join(
        (
            str(manifest.get("status") or ""),
            str(manifest.get("description") or ""),
            str(eval_block.get("known_limits") or ""),
        )
    )
    return _has_token(blob, SIM_ONLY_TOKENS)


def deploy_hint(repo: str, manifest: dict[str, Any] | None) -> str:
    if not manifest:
        return (
            f"microduck-skill: no manifest.json; if you own a duck and this is a walk: "
            f"sudo robotctl policy load walk {repo}"
        )
    name = str(manifest.get("name") or "policy")
    if is_sim_only(manifest):
        return (
            f"microduck-skill: {repo} ({name}) is marked sim-only in the manifest; "
            "do not robotctl unless the owner accepts that"
        )
    if twist_is_velocity(manifest):
        return f"microduck-skill: if you own a duck: sudo robotctl policy load walk {repo}"
    slot = name.replace(" ", "-")
    return f"microduck-skill: if you own a duck: sudo robotctl policy add {slot} {repo}"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: hub_manifest.py hint USER/NAME [manifest.json]", file=sys.stderr)
        print("       hub_manifest.py check-start [manifest.json]", file=sys.stderr)
        print("       hub_manifest.py is-behavior [manifest.json]", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "hint":
        repo = sys.argv[2] if len(sys.argv) > 2 else ""
        path = sys.argv[3] if len(sys.argv) > 3 else ""
        print(deploy_hint(repo, load_manifest(path) if path else None))
        return 0
    if cmd == "check-start":
        path = sys.argv[2] if len(sys.argv) > 2 else ""
        if is_episodic(load_manifest(path) if path else None):
            print(
                "microduck-skill: this repo is episodic (a short graph, not the standing body). "
                "start a walk/stand ONNX, pull --as NAME, then do NAME",
                file=sys.stderr,
            )
            return 2
        return 0
    if cmd == "is-behavior":
        path = sys.argv[2] if len(sys.argv) > 2 else ""
        return 0 if is_behavior_extra(load_manifest(path) if path else None) else 2
    print("usage: hub_manifest.py hint|check-start|is-behavior ...", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
