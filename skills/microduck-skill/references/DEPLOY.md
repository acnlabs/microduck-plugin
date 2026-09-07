# Deploy

Deploy is in scope. After every Hub publish, print the install lines for **this run's** repo. Do not hardcode a sample policy.

Default: **print, then wait.** Run `robotctl` / `ssh` only if the user explicitly asks to install on a real Microduck they own. A bad policy can beat XL330s. Sim metrics can pass while the video (or the floor) fails.

## Rehearse in sim first

Watch a checkpoint in the training env (localhost Viser, optional local mp4):

```bash
$SKILL/scripts/play.sh Mjlab-Velocity-Flat-MicroDuck --checkpoint-file /path/model_N.pt
```

ONNX / runtime contract (CPU MuJoCo, not Viser) — prefer the skill wrapper (localhost HTTP, official `infer_policy`, `--new-cmd-obs`):

```bash
$SKILL/scripts/control.sh start --onnx "$MICRODUCK_RL_ROOT/.microduck-plugin-export.onnx" --detach
# or a community / own Hub repo:
$SKILL/scripts/control.sh start --repo <user>/microduck-walk --detach
$SKILL/scripts/control.sh twist --x 0.25
$SKILL/scripts/control.sh head --yaw 0.4
$SKILL/scripts/control.sh status
$SKILL/scripts/control.sh shutdown
```

`--viewer` if you want the native window (macOS: `mjpython`). Raw official CLI is still valid:

```bash
uv run scripts/infer_policy.py --walking output.onnx --new-cmd-obs
# hot-swap rehearsal — same 61D contract the runtime uses
uv run scripts/infer_policy.py --walking walk.onnx --standing stand.onnx \
  --sitstand sitstand.onnx --new-cmd-obs
```

Posture flags live in a command slot. All-zero command means "stand", which looks like "the button does nothing".

## Install lines to print

Episodic community policy:

```bash
sudo robotctl policy add <skill-name> <user>/microduck-<name>
robotctl robot do <skill-name>
```

Held perpetual pose (owner picks hold time):

```bash
sudo robotctl policy add <skill-name> <user>/microduck-<name> --hold 5
```

Replace a gait slot (only if this repo is still a walk — read the printed hint):

```bash
sudo robotctl policy load walk <user>/microduck-my-walk
```

`control.sh start --repo` prints the hint from `manifest.json`. A remapped policy uses `policy add <name>`, not `load walk`. If the card says sim-only, print that and do not treat it as a walk install.

Health / updates (only if the user is debugging a board):

```bash
robotctl monitor
robotctl configure
# updates are signed, health-gated, reversible
```

Bluetooth-only laptop path is `duckctl` (no wifi, no ssh). Same rule: do not invoke it unless asked.

## Still not automatic

- No robot / user did not ask to install → stop after printing. The loop still includes this stage.
- User asked to install on a duck they own → run the printed `robotctl` for this repo only.
- Battery, clear floor, and a human watching the first run are the user's problem. Do not claim the duck learned it until they say so.
