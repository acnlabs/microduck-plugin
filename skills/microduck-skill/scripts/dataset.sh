#!/usr/bin/env bash
# Pack/check/replay control recordings. Not Jobs. Not train.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
usage:
  dataset.sh check FILE|DIR [FILE|DIR...]
  dataset.sh pack FILE|DIR [FILE|DIR...] --out DIR
  dataset.sh replay FILE|DIR --onnx PATH [--actions] [--max-steps N]

check/pack need only python3. replay uses the official infer_policy loop.
Command replay (default) re-asks what the agent asked. --actions plays motors.
train.sh does not read this dataset yet.
EOF
}

CMD="${1:-}"
[ -n "$CMD" ] || { usage; die "usage: dataset.sh check|pack|replay"; }
shift || true

case "$CMD" in
  check)
    [ $# -ge 1 ] || { usage; die "check requires FILE or DIR"; }
    exec python3 "$SCRIPT_DIR/dataset.py" check "$@"
    ;;
  pack)
    OUT=""
    PATHS=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --out) OUT="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) PATHS+=("$1"); shift ;;
      esac
    done
    [ ${#PATHS[@]} -ge 1 ] || die "pack requires FILE or DIR"
    [ -n "$OUT" ] || die "pack requires --out DIR"
    exec python3 "$SCRIPT_DIR/dataset.py" pack "${PATHS[@]}" --out "$OUT"
    ;;
  replay)
    RECORD=""
    ONNX=""
    ACTIONS=0
    MAX_STEPS=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --onnx) ONNX="${2:-}"; shift 2 ;;
        --record) RECORD="${2:-}"; shift 2 ;;
        --actions) ACTIONS=1; shift ;;
        --max-steps) MAX_STEPS="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *)
          if [ -z "$RECORD" ]; then
            RECORD="$1"
            shift
          else
            die "unknown replay arg: $1"
          fi
          ;;
      esac
    done
    [ -n "$RECORD" ] || die "replay requires FILE|DIR (or --record)"
    [ -n "$ONNX" ] || die "replay requires --onnx PATH"
    [ -f "$ONNX" ] || die "--onnx is not a file: $ONNX"
    require_cmd uv
    require_cmd python3
    resolve_rl_root
    ONNX="$(cd "$(dirname "$ONNX")" && pwd)/$(basename "$ONNX")"
    echo "microduck-skill: gate walk $ONNX"
    uv run --with onnx python3 "$SCRIPT_DIR/gate_check.py" "$ONNX" >/dev/null
    echo "microduck-skill: gate ok walk"
    ARGS=(--record "$RECORD" --onnx "$ONNX" --rl-root "$RL_ROOT")
    [ "$ACTIONS" -eq 1 ] && ARGS+=(--actions)
    [ -n "$MAX_STEPS" ] && ARGS+=(--max-steps "$MAX_STEPS")
    PY="$RL_ROOT/.venv/bin/python"
    if [ ! -x "$PY" ]; then
      cd "$RL_ROOT"
      exec uv run python "$SCRIPT_DIR/replay.py" "${ARGS[@]}"
    fi
    exec "$PY" "$SCRIPT_DIR/replay.py" "${ARGS[@]}"
    ;;
  -h|--help) usage; exit 0 ;;
  *) usage; die "unknown command: $CMD" ;;
esac
