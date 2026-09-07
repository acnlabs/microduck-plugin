# Sim control

Drive gated `[1,61]→[1,14]` ONNX files on localhost the same way `infer_policy` does (BAM M6, 50 Hz, `--new-cmd-obs`). This is the agent-facing API for **every command and skill slot**. Quality depends on whether that slot was trained. It is not Jobs, not Viser, and not `robotctl`.

`play.sh` watches a **training checkpoint**. `control.sh` drives **runtime ONNX**.

## Start

```bash
$SKILL/scripts/control.sh start --onnx "$MICRODUCK_RL_ROOT/.microduck-plugin-export.onnx" --detach \
  --record "$MICRODUCK_RL_ROOT/.microduck-plugin-record.jsonl"
# find Hub repos that already have policy.onnx (not a store, not a ranking):
$SKILL/scripts/control.sh search
$SKILL/scripts/control.sh search flamingo
# then fetch one (downloads policy.onnx, then gates):
$SKILL/scripts/control.sh start --repo <user>/microduck-walk --detach
$SKILL/scripts/control.sh pull <user>/microduck-sitstand --as sitstand
```

`search` queries Hugging Face and prints repos that contain `policy.onnx`. Downloads/likes are Hub counts, not quality. The **script** does not start a server or a train. **You** (the agent) do the next step: pick one by name/README, tell the human which repo, then `start --repo` / `pull --as`, gate, and try it in sim. Do not hand the CLI back. Do not start a train from a search hit. Gate + what the sim actually does remain the filter.

`--repo` and `--onnx` are exclusive. `pull --as` copies extras into `$MICRODUCK_RL_ROOT/.microduck-plugin-skills/` so the next `start` auto-loads them. Optional local extras: `--standing` `--sitstand` `--sit` `--slope` `--ground-pick` `--kick-left` `--kick-right` `--roulade`.

If a flag is omitted, start also loads any matching file in `$MICRODUCK_RL_ROOT/.microduck-plugin-skills/`. Kick ONNX switches the scene to the official ball XML. `--bind` stays localhost.

## Command

The 13D block is always the same slots (`twist` / `head` / `body`). **Meaning and range come from the loaded policy**, not from walk. Read `status.command_notes` before you twist. If the Hub repo has `manifest.json`, we load it next to `policy.onnx`. Walk velocity caps apply only when there is no remapping in the manifest (no `command` / description of flags). A `command.twist` list, or a description like `twist = [flag, side, 0]`, uses ±1 so a `1` is not chopped into `0.3`. Missing `manifest.json` stays walk and is printed, not silent.

```bash
$SKILL/scripts/control.sh twist --x 0.25   # walk: m/s. flamingo: flag (see status)
$SKILL/scripts/control.sh head --yaw 0.4
$SKILL/scripts/control.sh body --z 0.02
$SKILL/scripts/control.sh stop          # zeros twist only
```

| Slot | Walk default (no remap) | Otherwise |
|---|---|---|
| twist | x ±0.3 m/s, y ±0.2 m/s, yaw ±1.5 rad/s | ±1 per slot if the manifest remaps them |
| head | neck/pitch ±1.10, yaw ±1.40, roll ±0.31 rad | same mechanical caps |
| body | xy ±0.02 m, z ±0.03 m, angles ±30° | same mechanical caps |

`status.body_state` is this robot, not a skill score. Same card for every ONNX: trunk pose, projected gravity / `upright` / `tilt_deg` (angle from vertical, same gravity the policy sees), `ang_vel` and `joints_rel_home` from the 61D obs, `feet.left|right` from official `left_foot` / `right_foot` sites plus contact. Do not invent `fallen` or a per-trick metric. Say what the numbers are.

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
- Treat `search` as a store or ranking. It only lists Hub `policy.onnx`.
- Call this deploy ([DEPLOY.md](DEPLOY.md)).
- Claim a floor walk. This loop is sim only.
