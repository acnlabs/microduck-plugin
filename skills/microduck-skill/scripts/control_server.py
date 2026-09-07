#!/usr/bin/env python3
"""Localhost HTTP control loop for a gated Microduck ONNX.

Imports official infer_policy.PolicyInference from MICRODUCK_RL_ROOT
(same 61D / BAM path as the robot). Does not convert checkpoints.
Default is headless so an agent can drive the duck without a display.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from hub_manifest import (  # noqa: E402
    WALK_COMMAND_NOTES,
    WALK_TWIST_CAPS,
    behavior_duration_s,
    command_notes,
    load_manifest,
    twist_caps,
)


def _load_infer(rl_root: Path):
    path = rl_root / "scripts" / "infer_policy.py"
    if not path.is_file():
        raise SystemExit(f"microduck-skill: missing official infer_policy.py: {path}")
    spec = importlib.util.spec_from_file_location("microduck_infer_policy", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"microduck-skill: cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ControlState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.shutdown = False
        self.steps = 0
        self.record_path: Path | None = None
        self.record_fh: Any = None
        self.record_steps = 0
        self.manifest: dict[str, Any] | None = None
        self.twist_caps = dict(WALK_TWIST_CAPS)
        self.command_notes: dict[str, Any] = dict(WALK_COMMAND_NOTES)
        self.joint_names: list[str] = []
        self.foot_sites: dict[str, int | None] = {"left": None, "right": None}
        self.foot_geoms: dict[str, int | None] = {"left": None, "right": None}


def _register_behaviors(policy, specs: list[str]) -> None:
    import onnxruntime as ort

    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"microduck-skill: --behavior must be NAME=PATH, got {spec!r}")
        name, raw = spec.split("=", 1)
        name = name.strip()
        path = Path(raw).expanduser()
        if not name.isidentifier() or not name.islower():
            raise SystemExit(f"microduck-skill: bad behavior name {name!r}")
        if not path.is_file():
            raise SystemExit(f"microduck-skill: behavior onnx missing: {path}")
        if name in policy.behavior_sessions:
            print(f"microduck-skill: behavior {name} already loaded", flush=True)
            continue
        manifest = load_manifest(path.with_name(f"{name}.manifest.json")) or load_manifest(
            path.with_name("manifest.json")
        )
        duration = behavior_duration_s(manifest)
        policy.behavior_sessions[name] = ort.InferenceSession(str(path))
        policy.behavior_durations[name] = duration
        print(f"microduck-skill: behavior {name} {path.name} auto-return {duration:.1f}s", flush=True)


def _apply_manifest(state: ControlState, manifest: dict[str, Any] | None) -> None:
    state.manifest = manifest
    state.twist_caps = twist_caps(manifest)
    state.command_notes = command_notes(manifest)


class SkillResult:
    def __init__(self, skill: str, *, executed: bool, state: str, error: str | None = None) -> None:
        self.skill = skill
        self.executed = executed
        self.state = state
        self.error = error


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# Training / runtime caps for the 13D command (twist + head + body).
# Head: mechanical deltas from HOME in microduck_velocity_env_cfg.
# Body: infer_policy BODY_CMD_MAX_* (walk reward is ~0; slot is for API parity).
HEAD_KEYS = ("neck_pitch", "head_pitch", "head_yaw", "head_roll")
HEAD_ALIASES = {"neck": "neck_pitch", "pitch": "head_pitch", "yaw": "head_yaw", "roll": "head_roll"}
HEAD_CAPS = {"neck_pitch": 1.10, "head_pitch": 1.10, "head_yaw": 1.40, "head_roll": 0.31}
BODY_KEYS = ("x", "y", "z", "roll", "pitch", "yaw")
BODY_CAPS = {
    "x": 0.02,
    "y": 0.02,
    "z": 0.03,
    "roll": math.radians(30),
    "pitch": math.radians(30),
    "yaw": math.radians(30),
}


def _clamp_twist(state: ControlState, x: float, y: float, yaw: float) -> tuple[float, float, float]:
    caps = state.twist_caps
    x = max(-caps["x"], min(caps["x"], x))
    y = max(-caps["y"], min(caps["y"], y))
    yaw = max(-caps["yaw"], min(caps["yaw"], yaw))
    return x, y, yaw


def _pick(body: dict[str, Any], key: str, *aliases: str, default: Any = None) -> Any:
    if key in body:
        return body[key]
    for alias in aliases:
        if alias in body:
            return body[alias]
    return default


def _set_head(policy, body: dict[str, Any]) -> None:
    if body.get("reset"):
        policy.head_offset[:] = 0
    else:
        for i, key in enumerate(HEAD_KEYS):
            raw = _pick(body, key, *(a for a, k in HEAD_ALIASES.items() if k == key))
            if raw is None:
                continue
            cap = HEAD_CAPS[key]
            policy.head_offset[i] = max(-cap, min(cap, float(raw)))
    policy._update_command()


def _set_body(policy, body: dict[str, Any]) -> None:
    if body.get("reset"):
        policy.body_cmd[:] = 0
    else:
        for i, key in enumerate(BODY_KEYS):
            if key not in body:
                continue
            cap = BODY_CAPS[key]
            policy.body_cmd[i] = max(-cap, min(cap, float(body[key])))
    policy._update_command()


def _head_dict(policy) -> dict[str, float]:
    return {k: float(policy.head_offset[i]) for i, k in enumerate(HEAD_KEYS)}


def _body_dict(policy) -> dict[str, float]:
    return {k: float(policy.body_cmd[i]) for i, k in enumerate(BODY_KEYS)}


SKILL_ALIASES = {
    "pick": "ground_pick",
    "ground-pick": "ground_pick",
    "kick-left": "kick_left",
    "left-kick": "kick_left",
    "kick-right": "kick_right",
    "right-kick": "kick_right",
    "roll": "roulade",
    "sitstand": "sit",
    "stand": "stand",
}


def _skill_states(policy) -> dict[str, str]:
    flags = {
        "walking": policy.walking_session is not None,
        "standing": policy.standing_session is not None,
        "sit": policy.sit_session is not None,
        "sitstand": bool(policy.is_sitstand),
        "slope": policy.slope_session is not None,
        "ground_pick": policy.ground_pick_session is not None,
        "kick_left": "kick_left" in policy.behavior_sessions,
        "kick_right": "kick_right" in policy.behavior_sessions,
        "roulade": "roulade" in policy.behavior_sessions,
    }
    for name in policy.behavior_sessions:
        flags[name] = True
    return {name: ("loaded" if on else "untrained") for name, on in flags.items()}


def _set_sit(policy, on: bool) -> SkillResult:
    skill = "sit" if on else "stand"
    if policy.sit_session is None:
        return SkillResult(skill, executed=False, state="untrained")
    if policy.ground_pick_mode:
        return SkillResult(skill, executed=False, state="loaded", error="cannot sit during ground_pick")
    if policy.behavior_mode is not None:
        return SkillResult(skill, executed=False, state="loaded", error=f"cannot sit during {policy.behavior_mode}")
    if bool(policy.sit_mode) != bool(on):
        policy.toggle_sit()
    return SkillResult(skill, executed=True, state="loaded")


def _set_slope(policy, on: bool) -> SkillResult:
    if policy.slope_session is None:
        return SkillResult("slope", executed=False, state="untrained")
    if policy.behavior_mode is not None:
        return SkillResult("slope", executed=False, state="loaded", error=f"cannot slope during {policy.behavior_mode}")
    if bool(policy.slope_mode) != bool(on):
        policy.toggle_slope_mode()
    return SkillResult("slope", executed=True, state="loaded")


def _do_skill(policy, name: str) -> SkillResult:
    name = SKILL_ALIASES.get(name, name)
    if name == "sit":
        return _set_sit(policy, True)
    if name == "stand":
        return _set_sit(policy, False)
    if name == "slope":
        return _set_slope(policy, True)
    if name == "ground_pick":
        if policy.ground_pick_session is None:
            return SkillResult(name, executed=False, state="untrained")
        if policy.ground_pick_mode:
            return SkillResult(name, executed=False, state="loaded", error="ground_pick already running")
        if policy.sit_mode:
            return SkillResult(name, executed=False, state="loaded", error="cannot ground_pick while sitting")
        if policy.behavior_mode is not None:
            return SkillResult(name, executed=False, state="loaded", error=f"cannot ground_pick during {policy.behavior_mode}")
        policy.trigger_ground_pick()
        return SkillResult(name, executed=True, state="loaded")
    if name in policy.behavior_sessions:
        if policy.behavior_mode is not None:
            return SkillResult(name, executed=False, state="loaded", error=f"{policy.behavior_mode} already running")
        if policy.ground_pick_mode:
            return SkillResult(name, executed=False, state="loaded", error=f"cannot start {name} during ground_pick")
        if policy.sit_mode:
            return SkillResult(name, executed=False, state="loaded", error=f"cannot start {name} while sitting")
        if policy.slope_mode:
            return SkillResult(name, executed=False, state="loaded", error=f"cannot start {name} during slope")
        policy.trigger_behavior(name)
        return SkillResult(name, executed=True, state="loaded")
    if name in {"kick_left", "kick_right", "roulade"}:
        return SkillResult(name, executed=False, state="untrained")
    return SkillResult(name, executed=False, state="unknown", error=f"unknown skill: {name}")


def _skill_payload(policy, data, qpos_adr: int, state: ControlState, result: SkillResult) -> tuple[int, dict[str, Any]]:
    payload = _status(policy, data, qpos_adr, state)
    payload["executed"] = result.executed
    payload["skill"] = result.skill
    payload["skill_state"] = result.state
    if result.error:
        payload["error"] = result.error
    if result.state == "unknown":
        payload["ok"] = False
        return 400, payload
    if result.error and result.state == "loaded":
        payload["ok"] = False
        return 409, payload
    payload["ok"] = True
    return 200, payload


def _tilt_deg(projected_gravity: list[float]) -> float:
    upright = max(-1.0, min(1.0, -float(projected_gravity[2])))
    return math.degrees(math.acos(upright))


def _bind_body(state: ControlState, model) -> None:
    import mujoco

    names: list[str] = []
    for i in range(int(model.nu)):
        jid = int(model.actuator_trnid[i, 0])
        names.append(mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jid) or f"actuator_{i}")
    state.joint_names = names
    for side, site, geom in (
        ("left", "left_foot", "left_foot_collision"),
        ("right", "right_foot", "right_foot_collision"),
    ):
        sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, site)
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, geom)
        state.foot_sites[side] = sid if sid >= 0 else None
        state.foot_geoms[side] = gid if gid >= 0 else None


def _feet(model, data, state: ControlState) -> dict[str, dict[str, Any]]:
    contacts = {"left": False, "right": False}
    geom_to_side = {gid: side for side, gid in state.foot_geoms.items() if gid is not None}
    for i in range(int(data.ncon)):
        contact = data.contact[i]
        for gid in (int(contact.geom1), int(contact.geom2)):
            side = geom_to_side.get(gid)
            if side is not None:
                contacts[side] = True
    feet: dict[str, dict[str, Any]] = {}
    for side, sid in state.foot_sites.items():
        z = float(data.site_xpos[sid][2]) if sid is not None else None
        feet[side] = {"z_m": z, "contact": contacts[side]}
    return feet


def _body_state(policy, data, qpos_adr: int, state: ControlState) -> dict[str, Any]:
    xyz = [float(v) for v in data.qpos[qpos_adr : qpos_adr + 3]]
    quat = [float(v) for v in data.qpos[qpos_adr + 3 : qpos_adr + 7]]
    pg = [float(v) for v in policy.get_projected_gravity()]
    ang = [float(v) for v in policy.get_base_ang_vel()]
    rel = policy.get_joint_pos_relative()
    joints = {
        name: float(rel[i])
        for i, name in enumerate(state.joint_names)
        if i < len(rel)
    }
    return {
        "xyz": xyz,
        "quat": quat,
        "trunk_z_m": xyz[2],
        "ang_vel": ang,
        "projected_gravity": pg,
        "upright": -pg[2],
        "tilt_deg": _tilt_deg(pg),
        "joints_rel_home": joints,
        "feet": _feet(policy.model, data, state),
    }


def _status(policy, data, qpos_adr: int, state: ControlState) -> dict[str, Any]:
    with state.lock:
        twist = [float(v) for v in policy.vel_cmd]
        steps = state.steps
        policy_name = policy.current_policy
        head = _head_dict(policy)
        body = _body_dict(policy)
        skills = _skill_states(policy)
        sit_mode = bool(policy.sit_mode)
        behavior = policy.behavior_mode
        behavior_left = float(policy.behavior_time_left) if behavior else 0.0
        slope_mode = bool(policy.slope_mode)
        pick_mode = bool(policy.ground_pick_mode)
        record_steps = state.record_steps
        record_path = str(state.record_path) if state.record_path else None
    sense = _body_state(policy, data, qpos_adr, state)
    return {
        "ok": True,
        "policy": policy_name,
        "twist": {"x": twist[0], "y": twist[1], "yaw": twist[2]},
        "head": head,
        "body": body,
        "xyz": sense["xyz"],
        "trunk_z_m": sense["trunk_z_m"],
        "body_state": sense,
        "steps": steps,
        "sit_mode": sit_mode,
        "slope_mode": slope_mode,
        "ground_pick_mode": pick_mode,
        "behavior": behavior,
        "behavior_s_left": behavior_left,
        "skills": skills,
        "record": {"path": record_path, "steps": record_steps},
        "obs_contract": "61d_new_cmd",
        "command_notes": dict(state.command_notes),
    }


def make_handler(policy, data, qpos_adr: int, state: ControlState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("microduck-skill: control " + (fmt % args) + "\n")

        def do_GET(self) -> None:
            if urlparse(self.path).path == "/status":
                _json(self, 200, _status(policy, data, qpos_adr, state))
                return
            _json(self, 404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                _json(self, 400, {"ok": False, "error": "invalid json"})
                return
            if not isinstance(body, dict):
                _json(self, 400, {"ok": False, "error": "json object required"})
                return

            if path == "/twist":
                x = float(body.get("x", body.get("lin_vel_x", 0.0)))
                y = float(body.get("y", body.get("lin_vel_y", 0.0)))
                yaw = float(body.get("yaw", body.get("ang_vel_z", 0.0)))
                x, y, yaw = _clamp_twist(state, x, y, yaw)
                with state.lock:
                    policy.set_vel_cmd(x, y, yaw)
                _json(self, 200, _status(policy, data, qpos_adr, state))
                return
            if path == "/head":
                with state.lock:
                    _set_head(policy, body)
                _json(self, 200, _status(policy, data, qpos_adr, state))
                return
            if path == "/body":
                with state.lock:
                    _set_body(policy, body)
                _json(self, 200, _status(policy, data, qpos_adr, state))
                return
            if path == "/stop":
                with state.lock:
                    policy.set_vel_cmd(0.0, 0.0, 0.0)
                _json(self, 200, _status(policy, data, qpos_adr, state))
                return
            if path == "/sit":
                on = body.get("on", True)
                if isinstance(on, str):
                    on = on.lower() not in {"0", "false", "off", "no"}
                with state.lock:
                    result = _set_sit(policy, bool(on))
                code, payload = _skill_payload(policy, data, qpos_adr, state, result)
                _json(self, code, payload)
                return
            if path == "/stand":
                with state.lock:
                    result = _set_sit(policy, False)
                code, payload = _skill_payload(policy, data, qpos_adr, state, result)
                _json(self, code, payload)
                return
            if path == "/do":
                skill = str(body.get("skill", body.get("name", ""))).strip()
                if not skill:
                    _json(self, 400, {"ok": False, "error": "skill required"})
                    return
                with state.lock:
                    result = _do_skill(policy, skill)
                code, payload = _skill_payload(policy, data, qpos_adr, state, result)
                _json(self, code, payload)
                return
            if path == "/shutdown":
                with state.lock:
                    policy.set_vel_cmd(0.0, 0.0, 0.0)
                    state.shutdown = True
                _json(self, 200, {"ok": True, "shutdown": True})
                return
            _json(self, 404, {"ok": False, "error": "not found"})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Drive a gated Microduck ONNX on localhost")
    parser.add_argument("--onnx", required=True, help="Gated walking policy.onnx")
    parser.add_argument("--rl-root", required=True, help="pollen-robotics/microduck_rl checkout")
    parser.add_argument("--standing", default=None)
    parser.add_argument("--sitstand", default=None)
    parser.add_argument("--sit", default=None)
    parser.add_argument("--slope", default=None)
    parser.add_argument("--ground-pick", default=None)
    parser.add_argument("--kick-left", default=None)
    parser.add_argument("--kick-right", default=None)
    parser.add_argument("--roulade", default=None)
    parser.add_argument("--kick-duration", type=float, default=3.0)
    parser.add_argument("--roulade-duration", type=float, default=2.0)
    parser.add_argument("--ground-pick-period", type=float, default=4.0)
    parser.add_argument("--bind", default=os.environ.get("MICRODUCK_CONTROL_BIND", "127.0.0.1:8765"))
    parser.add_argument("--viewer", action="store_true", help="Open native MuJoCo (needs display / mjpython on macOS)")
    parser.add_argument(
        "--record",
        default=None,
        help="JSONL datacollect: obs[61], action[14], command[13], xyz, skill",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Hub manifest.json next to policy.onnx (command meaning / twist caps)",
    )
    parser.add_argument(
        "--behavior",
        action="append",
        default=[],
        help="Episodic extra NAME=PATH (same session swap as official kick/roulade)",
    )
    args = parser.parse_args()

    rl_root = Path(args.rl_root).resolve()
    onnx = Path(args.onnx).resolve()
    if not onnx.is_file():
        print(f"microduck-skill: --onnx is not a file: {onnx}", file=sys.stderr)
        return 2

    infer = _load_infer(rl_root)
    os.chdir(rl_root)

    import mujoco

    xml_path = infer.MICRODUCK_BALL_XML if (args.kick_left or args.kick_right) else infer.MICRODUCK_XML
    bam_model = infer.load_bam_model(infer.BAM_KP_FW, 7.4, None)
    model, data, bam_ctrl, _names = infer.load_mujoco_with_bam(
        xml_path, bam_model, 0.005, 0.1, infer.BAM_VIN_MIN
    )
    policy = infer.PolicyInference(
        model,
        data,
        bam_ctrl=bam_ctrl,
        walking_onnx_path=str(onnx),
        standing_onnx_path=args.standing,
        sitstand_onnx_path=args.sitstand,
        sit_onnx_path=args.sit,
        slope_onnx_path=args.slope,
        ground_pick_onnx_path=args.ground_pick,
        kick_left_onnx_path=args.kick_left,
        kick_right_onnx_path=args.kick_right,
        roulade_onnx_path=args.roulade,
        kick_duration=args.kick_duration,
        roulade_duration=args.roulade_duration,
        ground_pick_period=args.ground_pick_period,
        new_cmd_obs=True,
        use_projected_gravity=True,
    )
    state = ControlState()
    manifest_path = Path(args.manifest).expanduser() if args.manifest else onnx.with_name("manifest.json")
    _apply_manifest(state, load_manifest(manifest_path))
    policy.vel_max_x = state.twist_caps["x"]
    policy.vel_min_x = -state.twist_caps["x"]
    policy.vel_max_y = state.twist_caps["y"]
    policy.vel_min_y = -state.twist_caps["y"]
    policy.vel_max_ang = state.twist_caps["yaw"]
    policy.set_vel_cmd(0.0, 0.0, 0.0)
    _register_behaviors(policy, args.behavior)
    _bind_body(state, model)
    if state.manifest:
        print(
            f"microduck-skill: command from manifest {state.manifest.get('name')!r} "
            f"kind={state.manifest.get('kind')} twist_caps={state.twist_caps}",
            flush=True,
        )
    else:
        print(f"microduck-skill: no manifest; walk twist caps {state.twist_caps}", flush=True)

    freejoint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "trunk_base_freejoint")
    qpos_adr = int(model.jnt_qposadr[freejoint_id])
    data.qpos[qpos_adr + 0] = 0.0
    data.qpos[qpos_adr + 1] = 0.0
    data.qpos[qpos_adr + 2] = 0.125
    data.qpos[qpos_adr + 3 : qpos_adr + 7] = [1, 0, 0, 0]
    for i, qpos_idx in enumerate(policy.joint_qpos_indices):
        data.qpos[qpos_idx] = policy.default_pose[i]
    bam_ctrl.reset(data.qpos)
    policy.set_position_targets(policy.default_pose)
    mujoco.mj_forward(model, data)

    obs = policy.get_observations()
    if obs.size != 61:
        print(f"microduck-skill: expected 61D obs, got {obs.size}", file=sys.stderr)
        return 2

    host, _, port_s = args.bind.rpartition(":")
    host = host or "127.0.0.1"
    port = int(port_s or "8765")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print("microduck-skill: bind must be localhost (agent control is local-only)", file=sys.stderr)
        return 2

    if args.record:
        state.record_path = Path(args.record).expanduser().resolve()
        state.record_path.parent.mkdir(parents=True, exist_ok=True)
        state.record_fh = state.record_path.open("w", encoding="utf-8")

    server = ThreadingHTTPServer((host, port), make_handler(policy, data, qpos_adr, state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    skills = _skill_states(policy)
    print(f"microduck-skill: control listening http://{host}:{port}  onnx={onnx.name}", flush=True)
    print(f"microduck-skill: skills {skills}", flush=True)
    print(
        'microduck-skill: POST /twist /head /body /sit /stand /do /stop  GET /status  POST /shutdown',
        flush=True,
    )

    decimation = 4
    control_dt = decimation * float(model.opt.timestep)
    viewer = None
    if args.viewer:
        try:
            viewer = mujoco.viewer.launch_passive(model, data, show_left_ui=False, show_right_ui=False)
        except RuntimeError as exc:
            print(f"microduck-skill: viewer failed ({exc}); continuing headless", file=sys.stderr)
            viewer = None

    t0 = time.time()
    try:
        while True:
            step_start = time.time()
            with state.lock:
                if state.shutdown:
                    break
                if viewer is not None and not viewer.is_running():
                    break
                policy.update_ground_pick_phase(control_dt)
                policy.update_behavior(control_dt)
                obs = policy.get_observations()
                action = policy.infer()
                policy.apply_action(action)
                cmd = [float(v) for v in policy.vel_cmd]
                command = [float(v) for v in policy.command]
                head_snap = _head_dict(policy)
                body_snap = _body_dict(policy)
                policy_snap = policy.current_policy
                obs_list = [float(v) for v in obs]
                action_list = [float(v) for v in action]
            for _ in range(decimation):
                bam_ctrl.update()
                mujoco.mj_step(model, data)
            if viewer is not None:
                viewer.sync()
            xyz = [float(v) for v in data.qpos[qpos_adr : qpos_adr + 3]]
            with state.lock:
                state.steps += 1
                if state.record_fh is not None:
                    state.record_fh.write(
                        json.dumps(
                            {
                                "t": time.time() - t0,
                                "obs": obs_list,
                                "action": action_list,
                                "command": command,
                                "skill": policy_snap,
                                "twist": {"x": cmd[0], "y": cmd[1], "yaw": cmd[2]},
                                "head": head_snap,
                                "body": body_snap,
                                "xyz": xyz,
                            }
                        )
                        + "\n"
                    )
                    state.record_steps += 1
                    if state.record_steps % 50 == 0:
                        state.record_fh.flush()
            sleep = control_dt - (time.time() - step_start)
            if sleep > 0:
                time.sleep(sleep)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        if viewer is not None:
            viewer.close()
        if state.record_fh is not None:
            state.record_fh.flush()
            state.record_fh.close()
            print(f"microduck-skill: wrote {state.record_steps} steps to {state.record_path}", flush=True)
        print("microduck-skill: control stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
