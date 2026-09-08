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
play.sh is a viewer and does not exit. This script starts it, waits for the
clip, then stops the viewer. Play / upload failure prints "preview skipped"
and exits 0.
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

file_size() {
  if stat -f %z "$1" >/dev/null 2>&1; then
    stat -f %z "$1"
  else
    stat -c %s "$1"
  fi
}

has_flag() {
  local needle="$1" a
  for a in "${PLAY_ARGS[@]+"${PLAY_ARGS[@]}"}"; do
    case "$a" in
      "$needle"|"$needle"=*) return 0 ;;
    esac
  done
  return 1
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
  has_flag --num-envs || PLAY_ARGS+=(--num-envs 1)
  SINCE="$(date +%s)"
  WAIT_S="${MICRODUCK_PREVIEW_WAIT_S:-1800}"
  echo "microduck-skill: play for preview (cwd=$RL_ROOT, wait ${WAIT_S}s)"
  "$SCRIPT_DIR/play.sh" "$TASK" "${PLAY_ARGS[@]}" &
  PLAY_PID=$!
  stop_play() {
    if [ -n "${PLAY_PID:-}" ] && kill -0 "$PLAY_PID" 2>/dev/null; then
      kill "$PLAY_PID" 2>/dev/null || true
      sleep 1
      kill -9 "$PLAY_PID" 2>/dev/null || true
      wait "$PLAY_PID" 2>/dev/null || true
    fi
  }
  trap stop_play EXIT
  DEADLINE=$((SINCE + WAIT_S))
  FOUND=""
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if ! kill -0 "$PLAY_PID" 2>/dev/null; then
      wait "$PLAY_PID" || true
      PLAY_PID=""
      break
    fi
    if CAND="$(python3 "$SCRIPT_DIR/hub_preview.py" --find-root "$RL_ROOT" --since "$SINCE" 2>/dev/null)"; then
      S1="$(file_size "$CAND")"
      sleep 3
      S2="$(file_size "$CAND")"
      if [ "$S1" = "$S2" ] && [ "$S1" -gt 1000 ]; then
        FOUND="$CAND"
        break
      fi
    else
      sleep 5
    fi
  done
  stop_play
  trap - EXIT
  PLAY_PID=""
  [ -n "$FOUND" ] || skip "play wrote no mp4 under logs/**/videos/play/ within ${WAIT_S}s"
  MP4="$FOUND"
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
