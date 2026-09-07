#!/usr/bin/env python3
"""Replay a packed/control JSONL by feeding recorded 13D commands into infer_policy.

Default is command replay (what the agent asked). --actions plays motor targets
to sanity-check the tensors. Not train.sh. Not realtime.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dataset import episode_paths, read_episode
from control_server import _load_infer


def _apply_command(policy, command: list[float]) -> None:
    policy.vel_cmd[0] = command[0]
    policy.vel_cmd[1] = command[1]
    policy.vel_cmd[2] = command[2]
    policy.head_offset[:] = command[3:7]
    policy.body_cmd[:] = command[7:13]
    policy._update_command()


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay recorded Microduck commands in sim")
    parser.add_argument("--record", required=True, help="JSONL file or packed dataset directory")
    parser.add_argument("--onnx", required=True)
    parser.add_argument("--rl-root", required=True)
    parser.add_argument("--actions", action="store_true", help="Apply recorded actions instead of commands")
    parser.add_argument("--max-steps", type=int, default=0)
    args = parser.parse_args()

    rl_root = Path(args.rl_root).resolve()
    onnx = Path(args.onnx).resolve()
    src = Path(args.record)
    paths = episode_paths(src)
    rows: list[dict] = []
    for path in paths:
        rows.extend(read_episode(path))
    if args.max_steps > 0:
        rows = rows[: args.max_steps]
    if not rows:
        print("microduck-skill: replay has no steps", file=sys.stderr)
        return 2

    infer = _load_infer(rl_root)
    os.chdir(rl_root)
    import mujoco

    bam_model = infer.load_bam_model(infer.BAM_KP_FW, 7.4, None)
    model, data, bam_ctrl, _names = infer.load_mujoco_with_bam(
        infer.MICRODUCK_XML, bam_model, 0.005, 0.1, infer.BAM_VIN_MIN
    )
    policy = infer.PolicyInference(
        model,
        data,
        bam_ctrl=bam_ctrl,
        walking_onnx_path=str(onnx),
        new_cmd_obs=True,
        use_projected_gravity=True,
    )
    policy.vel_max_x = 0.3
    policy.vel_min_x = -0.3
    policy.vel_max_y = 0.2
    policy.vel_min_y = -0.2
    policy.vel_max_ang = 1.5

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

    decimation = 4
    drifts: list[float] = []
    min_z = 1.0
    mode = "actions" if args.actions else "commands"
    print(f"microduck-skill: replay {mode} steps={len(rows)} onnx={onnx.name}", flush=True)

    for step, row in enumerate(rows, start=1):
        command = [float(v) for v in row["command"]]
        _apply_command(policy, command)
        if args.actions:
            action = [float(v) for v in row["action"]]
            policy.apply_action(action)
            policy.last_action[:] = action
        else:
            action = policy.infer()
            policy.apply_action(action)
        for _ in range(decimation):
            bam_ctrl.update()
            mujoco.mj_step(model, data)
        xyz = [float(v) for v in data.qpos[qpos_adr : qpos_adr + 3]]
        rec = [float(v) for v in row["xyz"]]
        drift = ((xyz[0] - rec[0]) ** 2 + (xyz[1] - rec[1]) ** 2 + (xyz[2] - rec[2]) ** 2) ** 0.5
        drifts.append(drift)
        min_z = min(min_z, xyz[2])
        if step == len(rows) or step % 100 == 0:
            print(
                f"microduck-skill: replay step {step}/{len(rows)} "
                f"xyz=({xyz[0]:.3f},{xyz[1]:.3f},{xyz[2]:.3f}) drift={drift:.3f}m",
                flush=True,
            )

    mean = sum(drifts) / len(drifts)
    peak = max(drifts)
    print(
        json.dumps(
            {
                "ok": True,
                "mode": mode,
                "steps": len(rows),
                "mean_drift_m": round(mean, 4),
                "max_drift_m": round(peak, 4),
                "min_trunk_z_m": round(min_z, 4),
                "stood": min_z > 0.06,
            }
        ),
        flush=True,
    )
    if min_z <= 0.06:
        print("microduck-skill: replay fell over (trunk_z <= 6cm)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
