# Deploy (gated)

Default: **print these commands. Do not run them.**

Run `robotctl` / `ssh` only if the user explicitly asks to install on a real Microduck they own. A bad policy can beat XL330s. Sim metrics can pass while the video (or the floor) fails.

## Rehearse in sim first

Watch a checkpoint in the training env (localhost Viser, optional local mp4):

```bash
$SKILL/scripts/play.sh Mjlab-Velocity-Flat-MicroDuck --checkpoint-file /path/model_N.pt
```

ONNX / runtime contract (CPU MuJoCo, not Viser) from `MICRODUCK_RL_ROOT`:

```bash
uv run scripts/infer_policy.py --walking output.onnx
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

Replace a gait slot:

```bash
sudo robotctl policy load walk <user>/microduck-my-walk
```

Health / updates (only if the user is debugging a board):

```bash
robotctl monitor
robotctl configure
# updates are signed, health-gated, reversible
```

Bluetooth-only laptop path is `duckctl` (no wifi, no ssh). Same rule: do not invoke it unless asked.

## Still not automatic

- No robot on the network → stop after Hub publish.
- User has not said "install on the robot" → stop after printing.
- Battery, clear floor, and a human watching the first run are the user's problem. Do not claim the duck learned it until they say so.
