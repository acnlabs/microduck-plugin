---
name: microduck-skill
description: Train, export, and publish Microduck reinforcement-learning policies (PPO on MuJoCo Warp via mjlab), then print gated robotctl commands. Use when the user wants to teach a Microduck a new trick, train a gait or episodic policy, run microduck_rl, export ONNX, publish to Hugging Face Hub, or use Hugging Face Jobs. Do not SSH or run robotctl unless the user explicitly asks to install on a real robot.
license: MIT
compatibility: "Requires uv, HF_TOKEN, and MICRODUCK_HF_NAMESPACE (Jobs is the default trainer). Optional: WANDB_API_KEY, MICRODUCK_RL_ROOT, MICRODUCK_TRAIN_LOCAL=1 (needs NVIDIA CUDA). Real-robot deploy needs explicit user approval."
metadata:
  author: acnlabs
  version: "0.1.6"
  upstream_rl: "https://github.com/pollen-robotics/microduck_rl"
  upstream_runtime: "https://github.com/pollen-robotics/microduck"
  default_train: "hf-jobs"
---

# Microduck RL

Close the software loop: **spec → sim → package → Hub**. You are training a 61→14 PPO policy, not an LLM.

Canonical playbook: `AGENTS.md` in `pollen-robotics/microduck_rl`. This skill is the job ticket; that file wins if they disagree.

`$SKILL` = directory that contains this `SKILL.md`. Always invoke scripts with that absolute path. The skill id is `microduck-skill`.

## Preconditions

1. Run `$SKILL/scripts/doctor.sh` (add `--clone --sync` if there is no checkout). It must print `doctor ok`.
2. Default compute is **Hugging Face Jobs**. Require `HF_TOKEN` (or `hf auth login`) **and** `MICRODUCK_HF_NAMESPACE` (user or org). No namespace → Jobs prompts and the agent hangs.
3. Local train only if `MICRODUCK_TRAIN_LOCAL=1` **and** CUDA is present. Smoke uses the same switch.
4. Stop if doctor fails. Do not invent another trainer (Isaac Sim, AutoTrain, Colab-only hacks).

## Hard rules

- Never skip the 64-env × 5-iter smoke test (`$SKILL/scripts/smoke.sh`).
- Never hand-convert a `.pt` to ONNX. Only upstream `scripts/export.py`.
- Observation stays **61D**; action stays **14D**. Unused command slots are zero-padded, never deleted.
- Do not hardcode joint indices. Servo helpers in `mdp.py` only.
- Community publish is **constant-command** episodic/perpetual only. Phase / posture-flag stay official.
- **Do not run `robotctl` / SSH** unless the user explicitly says to install on a real robot. Print the commands.

## Workflow (do not skip stages)

1. **Spec** — one-line behavior, `kind` (`episodic` | `perpetual`), closest template. [references/TRAIN.md](references/TRAIN.md).
2. **Sim** — edit env → CPU `pytest tests/` → `$SKILL/scripts/smoke.sh` → `$SKILL/scripts/train.sh` → wandb (main task term rising; penalty `Episode_Reward/*` ≤ 0).
3. **Package** — `$SKILL/scripts/export_publish.sh`. [references/PUBLISH.md](references/PUBLISH.md).
4. **Deploy (gated)** — print lines from [references/DEPLOY.md](references/DEPLOY.md). Wait.

## Scripts

| Script | Does |
|---|---|
| `scripts/doctor.sh [--clone] [--sync]` | Tools, checkout, Jobs env. |
| `scripts/smoke.sh <TASK_ID>` | 64×5. Jobs unless `MICRODUCK_TRAIN_LOCAL=1`. |
| `scripts/train.sh <TASK_ID> [args…]` | Same compute switch. Default 4096 envs. |
| `scripts/gate_check.py <policy.onnx>` | `[1,61]→[1,14]`; skip initializers. Called via `uv run --with onnx`. |
| `scripts/export_publish.sh …` | Official export to `$RL_ROOT/output.onnx` only, then Hub. |

## Report back

Say what rolled out ("bows, then face-plants 1 in 3"), not "it works". Training is hours — submit Jobs, then wait.
