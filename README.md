# Microduck Agent Plugin

[![CI](https://github.com/acnlabs/microduck-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/acnlabs/microduck-plugin/actions/workflows/ci.yml)

**https://github.com/acnlabs/microduck-plugin** · [Agent Plugins 1.0](https://agent-plugins.org) package for the Microduck train → export → Hub → robot loop.

This is **not** the robot firmware. That repo is [`pollen-robotics/microduck`](https://github.com/pollen-robotics/microduck). Compatible clients discover this folder via `plugin.json`, then load the skill `microduck-skill`.

```text
microduck-plugin/
├── plugin.json
├── LICENSE
├── README.md
└── skills/microduck-skill/
```

## Install

Clone this repository. Add **the directory that contains `plugin.json`** to an [Agent Plugins](https://agent-plugins.org) client (Cursor, GitHub Copilot, ChatGPT/Codex, VS Code, Kiro). Do not add only `skills/microduck-skill` if the client supports plugins.

```bash
git clone https://github.com/acnlabs/microduck-plugin
# Point the client at that folder (the one with plugin.json).
```

If the client only scans Agent Skills (not plugins):

```bash
npx skills add acnlabs/microduck-plugin@microduck-skill -g -y
```

Or point it at `skills/microduck-skill` after a clone.

ClawHub listing for `microduck-skill` is still pending review. Use GitHub / `npx skills add` until it is public.

## Worked examples (Hub, not bundled)

Walk and bow are **not** ONNX files in this repo. They are community Hub graphs this plugin's loop produced. Not official Pollen policies.

| Policy | Hub | kind |
|---|---|---|
| walk | https://huggingface.co/neil-jo/microduck-walk | perpetual gait |
| polite-bow | https://huggingface.co/neil-jo/microduck-polite-bow | episodic 4s |

Localhost (agent runs `control.sh`; do not paste these for a human to type):

```bash
$SKILL/scripts/control.sh start --repo neil-jo/microduck-walk --detach
$SKILL/scripts/control.sh pull neil-jo/microduck-polite-bow --as polite_bow
$SKILL/scripts/control.sh do polite_bow
```

Do not `start --repo` the bow graph. After publish, print `robotctl` for **this run's** repo. Run those commands only if the user owns a Microduck and asks to install.

**v0 scope:** new behavior → smoke → train (default: Hugging Face Jobs, requires `MICRODUCK_HF_NAMESPACE`) → official ONNX export → Hub publish → localhost sim control → deploy. Optional `wandb login` turns on webpage curves. Jobs cannot record `--video` (no OpenGL). `play.sh` is local Viser + local mp4 (training checkpoint). The agent runs `control.sh` (search / start / twist / `do`) itself — do not expect the human to type those. After publish the skill always prints `robotctl` for that repo. It runs those commands only if you explicitly ask to install on a Microduck you own.

Package CI (no GPU): `python3 scripts/ci_check.py`

Ready-check (needs `uv` and a Hugging Face login):

```bash
./skills/microduck-skill/scripts/doctor.sh --clone --sync
export MICRODUCK_RL_ROOT=...
export MICRODUCK_HF_NAMESPACE=<hf-user-or-org>
```

Upstream:

- Runtime: https://github.com/pollen-robotics/microduck
- Training: https://github.com/pollen-robotics/microduck_rl (`AGENTS.md`)

Related (local GPU box / CLI, not this Jobs-first plugin): [microduck-mcp](https://github.com/aj-dev-smith/microduck-mcp), [microduck-cli](https://pypi.org/project/microduck-cli/).
