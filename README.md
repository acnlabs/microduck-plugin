# Microduck Agent Plugin

[![CI](https://github.com/acnlabs/microduck-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/acnlabs/microduck-plugin/actions/workflows/ci.yml)

**https://github.com/acnlabs/microduck-plugin** · [Agent Plugins 1.0](https://agent-plugins.org) package for the Microduck train → export → Hub publish loop.

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

How the client is told to load a plugin directory is client-specific. Two portable options:

```bash
git clone https://github.com/acnlabs/microduck-plugin
# Point the client at that folder (the one with plugin.json).
```

If the client only scans Agent Skills (not plugins), point it at `skills/microduck-skill`.

**v0 scope:** new behavior → smoke → train (default: Hugging Face Jobs, requires `MICRODUCK_HF_NAMESPACE`) → official ONNX export → Hub publish. Optional `wandb login` turns on webpage curves and `--video` clips. `play.sh` is local Viser, not Jobs. `robotctl` is printed, not executed, unless you explicitly ask to install on a real robot.

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
