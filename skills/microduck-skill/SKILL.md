---
name: microduck-skill
description: Train, export, publish, drive a simulated Microduck over localhost HTTP, and deploy Microduck reinforcement-learning policies (PPO on MuJoCo Warp via mjlab) onto a real robot via robotctl. Use when the user wants to teach a Microduck a new trick, train a gait or episodic policy, run microduck_rl, export ONNX, command a sim duck, publish to Hugging Face Hub, use Hugging Face Jobs, or install a published policy on a duck they own. After Hub publish, try preview.sh (preview.mp4 on that card; skip if play cannot record). Always walk deploy. Print robotctl; run it only when that user explicitly asks to install on their robot. Never SSH or robotctl on a machine they do not own.
license: MIT
compatibility: "Requires uv, HF_TOKEN, and MICRODUCK_HF_NAMESPACE (Jobs is the default trainer). Optional: WANDB_API_KEY, MICRODUCK_RL_ROOT, MICRODUCK_TRAIN_LOCAL=1 (needs NVIDIA CUDA). Real-robot deploy needs explicit user approval."
metadata:
  author: acnlabs
  version: "0.1.15"
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
3. **Package** — `$SKILL/scripts/export_publish.sh`. [references/PUBLISH.md](references/PUBLISH.md). After a tensorboard run, export from `--checkpoint-file` (or an already-gated `--onnx`), not a wandb path. Then try `$SKILL/scripts/preview.sh --repo <this-run-repo> --task …` (or `--mp4` if a clip already exists). That is a sim checkpoint replay on **this** Hub card (`preview.mp4`), not ONNX control, not a robot, not a ranking. Play/upload failure is not a failed publish — say `preview skipped` and continue. Do not put mp4 in the plugin git.
4. **Sim control** — you run `$SKILL/scripts/control.sh` yourself (localhost HTTP). Do not paste these commands for the human to type. `search` lists Hub `policy.onnx` (not a store). You pick a repo by name/README match, then `start --repo` / `pull --as`. Worked Hub examples (not bundled, not official Pollen): `neil-jo/microduck-walk` (perpetual; `start --repo`) and `neil-jo/microduck-polite-bow` (`pull --as` then `do`). Read `status.command_notes` before twisting — walk speed caps are not universal. Read `status.body_state` to say what the body did (`tilt_deg`, feet, joints vs HOME) — same card for every policy. Do not call it fallen. Episodic Hub graphs: `pull --as name` then `do name` (same swap as kick). Do not `start --repo` them. Exercise twist/head/`do`, and report from that card. [references/CONTROL.md](references/CONTROL.md). `status.skills` is `loaded` or `untrained`. `--record` + `dataset.sh` is datacollect only. Bind stays localhost. Do not start a train from a search hit.
5. **Deploy** — always this stage after publish. Print the install lines from [references/DEPLOY.md](references/DEPLOY.md) for **this run's** `--repo` (never a hardcoded test repo). If the user explicitly says to install on a Microduck they own, run those `robotctl` lines. If they have no robot or did not ask, stop after printing. Do not claim hardware success until they report it.

## Scripts

| Script | Does |
|---|---|
| `scripts/doctor.sh [--clone] [--sync]` | Tools, checkout, Jobs env. |
| `scripts/smoke.sh <TASK_ID>` | 64×5. Jobs unless `MICRODUCK_TRAIN_LOCAL=1`. wandb → curves; `--video` only on local CUDA. |
| `scripts/train.sh <TASK_ID> [args…]` | Same compute switch. Default 4096 envs. Same wandb/video rules. |
| `scripts/play.sh <TASK_ID> --checkpoint-file\|--wandb-run-path …` | Local Viser webpage + mp4. Checkpoint watch. Not Jobs. |
| `scripts/preview.sh --repo USER/NAME …` | Optional. `play.sh` (or `--mp4`) → Hub `preview.mp4` + README embed. Failure exits 0. Not a store. |
| `scripts/control.sh start\|search\|pull\|twist\|head\|body\|sit\|stand\|do\|stop\|status\|shutdown` | Agent runs these. Localhost 13D command. `search` lists Hub `policy.onnx`; you then `start --repo` / `pull`. Not Jobs. Not robotctl. |
| `scripts/dataset.sh check\|pack\|replay` | Validate/pack `--record` JSONL; replay commands in sim. Not consumed by train.sh. |
| `scripts/gate_check.py <policy.onnx>` | `[1,61]→[1,14]`; skip initializers. Called via `uv run --with onnx`. |
| `scripts/export_publish.sh …` | Official export to `$RL_ROOT/.microduck-plugin-export.onnx` only, then Hub. |

## Report back

Say what rolled out ("bows, then face-plants 1 in 3"), not "it works". Training is hours — submit Jobs, then wait.
