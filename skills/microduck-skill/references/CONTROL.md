# Sim control

Drive gated `[1,61]→[1,14]` ONNX files on localhost the same way `infer_policy` does (BAM M6, 50 Hz, `--new-cmd-obs`). This is the agent-facing API for **every command and skill slot**. Quality depends on whether that slot was trained. It is not Jobs, not Viser, and not `robotctl`.

`play.sh` watches a **training checkpoint**. `control.sh` drives **runtime ONNX**.

## Start

```bash
$SKILL/scripts/control.sh start --onnx "$MICRODUCK_RL_ROOT/.microduck-plugin-export.onnx" --detach \
  --record "$MICRODUCK_RL_ROOT/.microduck-plugin-record.jsonl"
# or a published Hub repo (downloads policy.onnx, then gates):
$SKILL/scripts/control.sh start --repo <user>/microduck-walk --detach
$SKILL/scripts/control.sh pull <user>/microduck-sitstand --as sitstand
```

`--repo` and `--onnx` are exclusive. `pull --as` copies extras into `$MICRODUCK_RL_ROOT/.microduck-plugin-skills/` so the next `start` auto-loads them. Optional local extras: `--standing` `--sitstand` `--sit` `--slope` `--ground-pick` `--kick-left` `--kick-right` `--roulade`.

If a flag is omitted, start also loads any matching file in `$MICRODUCK_RL_ROOT/.microduck-plugin-skills/`. Kick ONNX switches the scene to the official ball XML. `--bind` stays localhost.

## Command

13D walk command (always accepted):

```bash
$SKILL/scripts/control.sh twist --x 0.25
$SKILL/scripts/control.sh head --yaw 0.4
$SKILL/scripts/control.sh body --z 0.02
$SKILL/scripts/control.sh stop          # zeros twist only
```

| Slot | Caps | Walk ONNX |
|---|---|---|
| twist | x ±0.3 m/s, y ±0.2 m/s, yaw ±1.5 rad/s | trained |
| head | neck/pitch ±1.10, yaw ±1.40, roll ±0.31 rad | trained |
| body | xy ±0.02 m, z ±0.03 m, angles ±30° | slot only |

Skills are always valid verbs. `status.skills` is `loaded` or `untrained` (no weight yet). Untrained `do` / `sit` returns HTTP 200, `executed: false`, `skill_state: "untrained"`. 409 is only a real conflict (e.g. kick while sitting).

```bash
$SKILL/scripts/control.sh sit
$SKILL/scripts/control.sh stand
$SKILL/scripts/control.sh do kick_left
$SKILL/scripts/control.sh status
```

## Record (datacollect)

`--record FILE` streams JSONL, one control step per line, the tensors the policy actually saw and emitted:

| field | shape / meaning |
|---|---|
| `obs` | 61 floats |
| `action` | 14 floats |
| `command` | 13 floats (twist + head + body) |
| `skill` | active policy name |
| `xyz` | trunk world position |
| `t` | seconds since start |

Check and pack, then replay the agent's commands in sim (does not train):

```bash
$SKILL/scripts/dataset.sh check "$MICRODUCK_RL_ROOT/.microduck-plugin-record.jsonl"
$SKILL/scripts/dataset.sh pack "$MICRODUCK_RL_ROOT/.microduck-plugin-record.jsonl" \
  --out "$MICRODUCK_RL_ROOT/.microduck-plugin-dataset"
$SKILL/scripts/dataset.sh replay "$MICRODUCK_RL_ROOT/.microduck-plugin-dataset" \
  --onnx "$MICRODUCK_RL_ROOT/.microduck-plugin-export.onnx"
```

`train.sh` cannot read this dataset. Official `uv run train` is on-policy PPO with no demo ingest. mjlab's only file trajectory is `motion.npz` on tracking tasks (not Microduck). See [TRAIN.md](TRAIN.md) § Agent recordings. Do not invent `--from-record`.

## Do not

- Bind anything other than localhost.
- Hand-convert a `.pt`. Export + `gate_check.py` first.
- Command raw joints.
- Call this deploy ([DEPLOY.md](DEPLOY.md)).
- Claim a floor walk. This loop is sim only.
