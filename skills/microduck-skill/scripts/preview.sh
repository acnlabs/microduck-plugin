#!/usr/bin/env bash
# Optional Hub card preview: play.sh mp4 → preview.mp4. Never blocks publish. Not robotctl.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
usage:
  preview.sh --repo USER/NAME --task TASK_ID --checkpoint-file PATH [play extras]
  preview.sh --repo USER/NAME --task TASK_ID --wandb-run-path ENT/PROJ/RUN [play extras]
  preview.sh --repo USER/NAME --mp4 FILE

Uploads preview.mp4 to this run's Hub card and embeds it in README.
Checkpoint replay only — not ONNX control.sh, not a robot, not a ranking.
Play / upload failure prints "preview skipped" and exits 0.
EOF
}

REPO=""
TASK=""
MP4=""
PLAY_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --task) TASK="${2:-}"; shift 2 ;;
    --mp4) MP4="${2:-}"; shift 2 ;;
    --checkpoint-file|--wandb-run-path)
      PLAY_ARGS+=("$1" "${2:-}")
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) PLAY_ARGS+=("$1"); shift ;;
  esac
done

[ -n "$REPO" ] || { usage; die "preview.sh requires --repo USER/NAME"; }

skip() {
  echo "microduck-skill: preview skipped: $*" >&2
  exit 0
}

if [ -z "$MP4" ]; then
  [ -n "$TASK" ] || skip "need --task and a checkpoint, or pass --mp4"
  SOURCE=0
  for a in "${PLAY_ARGS[@]+"${PLAY_ARGS[@]}"}"; do
    case "$a" in
      --checkpoint-file|--wandb-run-path|--checkpoint-file=*|--wandb-run-path=*) SOURCE=1 ;;
    esac
  done
  [ "$SOURCE" -eq 1 ] || skip "need --checkpoint-file or --wandb-run-path, or pass --mp4"
  if [ -n "${MICRODUCK_RL_ROOT:-}" ] && is_rl_checkout "$MICRODUCK_RL_ROOT"; then
    RL_ROOT="$(cd "$MICRODUCK_RL_ROOT" && pwd)"
  elif is_rl_checkout "$PWD"; then
    RL_ROOT="$(pwd)"
  else
    skip "set MICRODUCK_RL_ROOT to a microduck_rl checkout"
  fi
  SINCE="$(date +%s)"
  echo "microduck-skill: play for preview (cwd=$RL_ROOT)"
  if ! "$SCRIPT_DIR/play.sh" "$TASK" "${PLAY_ARGS[@]}"; then
    skip "play.sh failed (Jobs has no GL; Mac CPU play is slow)"
  fi
  if ! MP4="$(python3 "$SCRIPT_DIR/hub_preview.py" --find-root "$RL_ROOT" --since "$SINCE")"; then
    skip "play wrote no mp4 under logs/**/videos/play/"
  fi
fi

[ -f "$MP4" ] || skip "not a file: $MP4"
have_hf_token || skip "HF_TOKEN (or hf auth login) required to upload"

echo "microduck-skill: upload preview.mp4 → $REPO"
RL_PY=""
if [ -n "${MICRODUCK_RL_ROOT:-}" ] && [ -x "${MICRODUCK_RL_ROOT}/.venv/bin/python" ]; then
  RL_PY="${MICRODUCK_RL_ROOT}/.venv/bin/python"
elif [ -n "${RL_ROOT:-}" ] && [ -x "${RL_ROOT}/.venv/bin/python" ]; then
  RL_PY="${RL_ROOT}/.venv/bin/python"
fi
if [ -n "$RL_PY" ]; then
  PY=("$RL_PY")
elif command -v uv >/dev/null 2>&1; then
  PY=(uv run --with huggingface_hub python3)
else
  PY=(python3)
fi
if ! "${PY[@]}" "$SCRIPT_DIR/hub_preview.py" --repo "$REPO" --mp4 "$MP4"; then
  skip "upload failed for $REPO"
fi
echo "microduck-skill: preview ok $REPO"
