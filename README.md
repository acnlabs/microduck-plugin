# Microduck Plugin

Standalone Agent Plugin (v1) for the Microduck train → export → Hub publish loop. Not the robot firmware (`pollen-robotics/microduck`). Sibling of `acn/`, `dsh-plugin-acn/`.

```text
microduck-plugin/
├── plugin.json              # name: microduck-plugin
├── LICENSE                  # MIT
├── README.md
└── skills/microduck-rl/     # the skill; keep this name
```

Compatible clients load `plugin.json`, then `skills/microduck-rl`.

In the agentplanet workspace, discovery is two symlinks only:

- `.cursor/skills/microduck-rl` → `microduck-plugin/skills/microduck-rl`
- `.agents/plugins/microduck-plugin` → `microduck-plugin/`

**v0 scope:** new behavior → smoke → train (default: Hugging Face Jobs, requires `MICRODUCK_HF_NAMESPACE`) → official ONNX export → Hub publish. `robotctl` is printed, not executed, unless the user explicitly asks to install on a real robot.

Ready-check:

```bash
./skills/microduck-rl/scripts/doctor.sh --clone --sync
export MICRODUCK_RL_ROOT=...
export MICRODUCK_HF_NAMESPACE=<hf-user-or-org>
```

This directory is its own git repo. `plugin.json` still has no `repository` until a remote exists — do not point it at `pollen-robotics/microduck_rl`. The parent agentplanet tree lists `microduck-plugin/` in `.gitignore`.

Upstream:

- Runtime: https://github.com/pollen-robotics/microduck
- Training: https://github.com/pollen-robotics/microduck_rl (`AGENTS.md`)

Related (different lane — local GPU box / CLI, not this Jobs-first plugin): [microduck-mcp](https://github.com/aj-dev-smith/microduck-mcp), [microduck-cli](https://pypi.org/project/microduck-cli/).
