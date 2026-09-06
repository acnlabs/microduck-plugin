# Microduck Agent Plugin

[Agent Plugins 1.0](https://agent-plugins.org) package for the Microduck train → export → Hub publish loop. Not the robot firmware (`pollen-robotics/microduck`). Sibling of `acn/`, `dsh-plugin-acn/`.

Clients that implement the spec discover this folder by `plugin.json`, then load `skills/microduck-rl`. The directory name stays `microduck-plugin` so it does not collide with the robot repo.

```text
microduck-plugin/
├── plugin.json              # name: microduck-plugin
├── LICENSE                  # MIT
├── README.md
└── skills/microduck-rl/     # the skill; keep this name
```

## Install

Compatible clients at launch include Cursor, GitHub Copilot, ChatGPT/Codex, VS Code, and Kiro. Pick one:

- Open / add **this directory** (the one with `plugin.json`) as a plugin. Do not add only `skills/microduck-rl`.
- Or symlink the plugin root into the workspace:

```bash
ln -sfn /path/to/microduck-plugin .agents/plugins/microduck-plugin
```

- Clients that only scan skills can additionally point at `skills/microduck-rl`.

In this agentplanet workspace those links already exist:

- `.agents/plugins/microduck-plugin` → `microduck-plugin/`
- `.cursor/skills/microduck-rl` → `microduck-plugin/skills/microduck-rl`

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
