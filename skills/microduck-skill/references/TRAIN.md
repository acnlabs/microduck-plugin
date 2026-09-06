# Train

Upstream: `AGENTS.md` in `pollen-robotics/microduck_rl`. Clone that repo; do not reinvent mjlab.

## What you are training

A PPO actor-critic (rsl_rl) at 50 Hz on **MuJoCo Warp** via **mjlab**. Physics is not Isaac Sim. Compute is an NVIDIA GPU — yours, or Hugging Face Jobs (`l4x1` default).

| | |
|---|---|
| Actor obs | 61 = 48 proprio + `[twist(3), head_pose(4), body_pose(6)]` |
| Actions | 14 XL330 servos. Beak is the 15th motor and is **not** in the net |
| Joint order (plain models) | 0–4 left leg, 5–8 neck/head, 9–13 right leg |
| Passive joints | all named `passive_*` (wheels, backlash). Select servos with `^(?!passive_).*` |

## Pick a template (do not start from mjlab base)

| Goal | Build on |
|---|---|
| Locomotion / new gait | velocity recipe (`make_microduck_velocity*_env_cfg`) |
| Episodic trick that ends in a pose | standup |
| Two commanded states | sitstand |
| Dynamic maneuver | roulade (read its cfg docstring) |

Copy DR / obs-noise / NaN-guards from the velocity stack. Standalone mjlab templates silently drop BAM + encoder bias + IMU misalignment.

Register the task in `src/mjlab_microduck/tasks/__init__.py`. Add a `-Backlash-` twin only if you also add it to `_BACKLASH_TASKS` and keep the same robot XML family.

## Invariants

- Unused command slots stay in the obs and are **zero-padded** with a tiny sampling range from step 0 (dead weights otherwise).
- Train the exact-zero command (`zero_command_prob`-style). Idle on the robot is all zeros.
- Never hardcode joint indices. Use `_servo_joint_ids` / `_servo_joint_pos` in `mdp.py`.
- BAM actuators: register `expand_bam_friction_fields`. Randomizing `dof_frictionloss` is a no-op.
- No action EMA / low-pass unless the runtime flag matches. Mismatched filtering breaks sim2real.
- Custom domain randomization must restore-then-apply. Accumulating DR ruined months of runs.

## Reward (read before editing weights)

- mjlab-base costs return ≥ 0 → **negative** weight.
- Microduck `*_penalty` / `*_l1` that already return ≤ 0 → **positive** weight. Wrong sign farms the violation.
- Infallible wandb check: every penalty `Episode_Reward/*` is **≤ 0**.
- No jackpots: "reach X" must be rate-limited or slewed. Early arrival that then pays per-step buys violence.
- Do not gate a positive reward on being fallen/low — the policy parks there.
- Encode the maneuver in hard state gates (contacts, orientation, latches), not small nudges.
- Watch the **main task term**, not only total reward (regularizers can rise while the trick never happens).

## Local checks, then smoke, then train

`$SKILL` = the directory that contains `SKILL.md`. Do not run `scripts/*.sh` relative to `microduck_rl`.

```bash
# once per machine
$SKILL/scripts/doctor.sh --clone --sync
export MICRODUCK_RL_ROOT=...          # doctor prints this
export MICRODUCK_HF_NAMESPACE=<hf-user-or-org>

cd "$MICRODUCK_RL_ROOT"
uv run list-envs
uv run --with pytest pytest tests/    # CPU; lock joint maps + reward signs

$SKILL/scripts/smoke.sh Mjlab-Your-Task-Id
$SKILL/scripts/train.sh Mjlab-Your-Task-Id --env.scene.num-envs 4096
```

Smoke is 64 envs × 5 iters, **same compute as train**: Hugging Face Jobs unless `MICRODUCK_TRAIN_LOCAL=1`. Official claim: catches ~95% of config errors. Never launch a long run without it.

Jobs **requires** `MICRODUCK_HF_NAMESPACE` (no interactive prompt). Billing is charged to that namespace — an org with no Jobs credits will 402 even if the personal account is funded. Optional: `MICRODUCK_HF_FLAVOR` (`l4x1` default), `MICRODUCK_HF_TIMEOUT`. Extra CLI args on `train.sh` are forwarded (`--detach`, `--agent.max_iterations`, …).

No `WANDB_API_KEY` / `~/.netrc` wandb login: `smoke.sh` / `train.sh` pass `--agent.logger tensorboard` and `--no-wandb`. Official `--no-wandb` only skips forwarding the key; without the logger switch the remote job dies at `wandb.init`.

With wandb logged in, the same scripts keep the official wandb logger and pass `--video`. Training writes short mp4s (`video_interval` 2000, `video_length` 200) and the runner uploads them to the run (project `mjlab_microduck`). `MICRODUCK_TRAIN_VIDEO=0` skips clips (curves still log). Replay on this machine:

```bash
$SKILL/scripts/play.sh Mjlab-Your-Task-Id --checkpoint-file /path/model_N.pt
# or --wandb-run-path <entity>/mjlab_microduck/<run_id>
```

`play.sh` defaults to `--viewer viser` (localhost webpage) and `--video` (mp4 under `logs/<experiment>/…/videos/play`). That clip stays local unless you upload it. `MICRODUCK_PLAY_VIDEO=0` or `MICRODUCK_PLAY_VIEWER=native` to change. Mac CPU play is slow.

Budgets at 4096 envs: simple episodic ≈ 1000 iters; gaits / recovery 4000–6000. A usable walk is often 1–2 hours.

## Reading a run

- wandb project `mjlab_microduck`; logs under `logs/<experiment_name>/`.
- Resume: `--agent.load-checkpoint model_XXXX.pt --agent.resume True`.
- When it "fails", eval the checkpoint (spawn batteries, end-state clusters) **before** rewriting rewards. Past failures were early ckpts or a bad success split.
- Report rollouts ("rolls, then face-plants 1 in 3"). The user decides good enough.

## Architecture footguns

- `uv sync` is ground truth. HF Jobs does a fresh sync; local-only pip installs die remotely.
- linux-aarch64 PyPI torch is CPU-only. Keep the repo's `[tool.uv.sources]` / exact `torch==` pin. Do not "clean up" that pin.
