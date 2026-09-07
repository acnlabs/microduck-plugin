---
name: microduck-skill
description: Train, export, publish, drive a simulated Microduck over localhost HTTP, and deploy Microduck reinforcement-learning policies (PPO on MuJoCo Warp via mjlab) onto a real robot via robotctl. Use when the user wants to teach a Microduck a new trick, train a gait or episodic policy, run microduck_rl, export ONNX, command a sim duck, publish to Hugging Face Hub, use Hugging Face Jobs, or install a published policy on a duck they own. After Hub publish, always walk deploy. Print robotctl; run it only when that user explicitly asks to install on their robot. Never SSH or robotctl on a machine they do not own.
license: MIT
compatibility: "Requires uv, HF_TOKEN, and MICRODUCK_HF_NAMESPACE (Jobs is the default trainer). Optional: WANDB_API_KEY, MICRODUCK_RL_ROOT, MICRODUCK_TRAIN_LOCAL=1 (needs NVIDIA CUDA). Real-robot deploy needs explicit user approval."
metadata:
  author: acnlabs
  version: "0.1.11"
  upstream_rl: "https://github.com/pollen-robotics/microduck_rl"
  upstream_runtime: "https://github.com/pollen-robotics/microduck"
  default_train: "hf-jobs"
---

# Microduck RL

Close the loop: **spec → sim → package → Hub → localhost control → robot**. You are training a 61→14 PPO policy, not an LLM. Hub publish is not the end — deploy is in scope. A published repo is a deliverable for whoever owns a duck, not a baked-in official weight.

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
2. **Sim** — edit env → CPU `pytest tests/` → `$SKILL/scripts/smoke.sh` → `$SKILL/scripts/train.sh`. If wandb is logged in, watch the run page (curves; Jobs cannot record `--video` — no GL in the image). Keep penalty `Episode_Reward/*` ≤ 0. If not, tensorboard + `--no-wandb` so Jobs do not hang. Replay a checkpoint with `$SKILL/scripts/play.sh` (Viser + local mp4).
3. **Package** — `$SKILL/scripts/export_publish.sh`. [references/PUBLISH.md](references/PUBLISH.md). After a tensorboard run, export from `--checkpoint-file` (or an already-gated `--onnx`), not a wandb path.
4. **Sim control** — `$SKILL/scripts/control.sh` (localhost HTTP). Load a local ONNX or `start --repo USER/NAME` / `pull --as sitstand`. [references/CONTROL.md](references/CONTROL.md). `status.skills` is `loaded` or `untrained`. `--record` + `dataset.sh` is datacollect only. Bind stays localhost.
5. **Deploy** — always this stage after publish. Print the install lines from [references/DEPLOY.md](references/DEPLOY.md) for **this run's** `--repo` (never a hardcoded test repo). If the user explicitly says to install on a Microduck they own, run those `robotctl` lines. If they have no robot or did not ask, stop after printing. Do not claim hardware success until they report it.

## Scripts

| Script | Does |
|---|---|
| `scripts/doctor.sh [--clone] [--sync]` | Tools, checkout, Jobs env. |
| `scripts/smoke.sh <TASK_ID>` | 64×5. Jobs unless `MICRODUCK_TRAIN_LOCAL=1`. wandb → curves; `--video` only on local CUDA. |
| `scripts/train.sh <TASK_ID> [args…]` | Same compute switch. Default 4096 envs. Same wandb/video rules. |
| `scripts/play.sh <TASK_ID> --checkpoint-file\|--wandb-run-path …` | Local Viser webpage + mp4. Checkpoint watch. Not Jobs. |
| `scripts/control.sh start\|pull\|twist\|head\|body\|sit\|stand\|do\|stop\|status\|shutdown` | Localhost 13D command. `start --repo` / `pull` fetch Hub `policy.onnx`. Not Jobs. Not robotctl. |
| `scripts/dataset.sh check\|pack\|replay` | Validate/pack `--record` JSONL; replay commands in sim. Not consumed by train.sh. |
| `scripts/gate_check.py <policy.onnx>` | `[1,61]→[1,14]`; skip initializers. Called via `uv run --with onnx`. |
| `scripts/export_publish.sh …` | Official export to `$RL_ROOT/.microduck-plugin-export.onnx` only, then Hub. |

## Report back

Say what rolled out ("bows, then face-plants 1 in 3"), not "it works". Training is hours — submit Jobs, then wait.
