# Publish

Package path is fixed. Viewer `play` applies the obs normalizer even if the ONNX does not — that hides a broken export.

## Export

From `MICRODUCK_RL_ROOT`:

```bash
uv run scripts/export.py <TASK_ID> --wandb-run-path <entity/project/run_id>
# or, after a Jobs/tensorboard run with no wandb:
uv run scripts/export.py <TASK_ID> --checkpoint-file /path/model_N.pt --onnx-file "$MICRODUCK_RL_ROOT/.microduck-plugin-export.onnx"
```

Then gate (from `MICRODUCK_RL_ROOT`; do not `find` other `.onnx` files):

```bash
uv run --with onnx python3 $SKILL/scripts/gate_check.py "$MICRODUCK_RL_ROOT/.microduck-plugin-export.onnx"
```

Refuse anything that is not `[1,61] → [1,14]`. Legacy 51-D graphs are invalid. Prefer the wrapper, which exports **only** to `$MICRODUCK_RL_ROOT/.microduck-plugin-export.onnx`, gates, then uploads `--onnx` (upstream `publish` rejects `--onnx` plus `--task`):

```bash
$SKILL/scripts/export_publish.sh \
  --task Mjlab-PoliteBow-Flat-MicroDuck \
  --wandb-run-path <entity/project/run_id> \
  --checkpoint 3000 \
  --repo <hf-user>/microduck-polite-bow \
  --kind episodic \
  --duration-s 4.0 \
  --description "Bows from a two-foot stand and comes back up."
```

## `kind` (manifest schema 2)

| kind | Meaning | What to pass |
|---|---|---|
| `episodic` | Runs `duration_s`, returns to a safe pose | `--duration-s`, optional `--chain` |
| `perpetual` gait | Runs until told otherwise; occupies a slot | `--slot walk` or `--slot stand` |
| `perpetual` held pose | Held until the owner ends it | `--unwind-s`, owner uses `--hold` on install |

`command.encoding`:

- absent / `constant` — community publish allowed
- `phase` (ground pick) or `posture_flag` (sit↔stand) — **refused** by `policy add`; official set only (`pollen-robotics/microduck-policies`)

Do not publish phase/posture-flag policies through this skill.

## Hub contract

`uv run publish` writes:

- `policy.onnx` (normalizer baked in)
- `manifest.json` schema 2 (`docs/policy-manifest.md` in `pollen-robotics/microduck`)
- README

It already checks graph shape, runs a NaN/constant-output smoke, fills the `training` block from git/wandb, and creates the repo **private** unless `--no-private`.

Need `HF_TOKEN` with write access to `--repo`. Repos look like `<user>/microduck-<name>`.

## After publish

Try a card preview for **this** `--repo`. Optional; never fail the publish if it skips:

```bash
$SKILL/scripts/preview.sh \
  --repo <hf-user>/microduck-polite-bow \
  --task Mjlab-PoliteBow-Flat-MicroDuck \
  --checkpoint-file /path/model_N.pt
# or, if play already wrote a clip:
$SKILL/scripts/preview.sh --repo <hf-user>/microduck-polite-bow --mp4 /path/clip.mp4
```

That uploads `preview.mp4` and embeds it in the Hub README. It is a `play.sh` checkpoint replay, not `control.sh` ONNX, not a robot, not a ranking. Jobs cannot record; Mac CPU play is slow. `preview skipped` is a valid outcome. Re-running `export_publish.sh` rewrites the official README and drops the embed — run `preview.sh` again after a republish.

Give the user the Hub URL and the **printed** install lines from [DEPLOY.md](DEPLOY.md). Do not SSH to a duck.
