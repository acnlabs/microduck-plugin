#!/usr/bin/env bash
# Local mjlab play: Viser webpage + optional mp4. Not Jobs. Not robotctl.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
usage: play.sh <TASK_ID> --checkpoint-file PATH | --wandb-run-path ENT/PROJ/RUN [play extras]

Defaults: --viewer viser (localhost webpage) and --video (mp4 under logs/.../videos/play).
MICRODUCK_PLAY_VIDEO=0 skips the local clip. MICRODUCK_PLAY_VIEWER=native|auto|viser.
Needs a display or a browser; CUDA helps, CPU is slow.
EOF
}

TASK_ID="${1:-}"
[ -n "$TASK_ID" ] || { usage; die "usage: play.sh <TASK_ID> --checkpoint-file PATH | --wandb-run-path ENT/PROJ/RUN"; }
shift

SOURCE=0
for a in "$@"; do
  case "$a" in
    --checkpoint-file|--wandb-run-path|--checkpoint-file=*|--wandb-run-path=*) SOURCE=1 ;;
  esac
done
[ "$SOURCE" -eq 1 ] || die "give --checkpoint-file or --wandb-run-path"

require_cmd uv
resolve_rl_root
cd "$RL_ROOT"

VIEWER="${MICRODUCK_PLAY_VIEWER:-viser}"
ARGS=("$TASK_ID" --viewer "$VIEWER")
if [ "${MICRODUCK_PLAY_VIDEO:-1}" != "0" ]; then
  ARGS+=(--video)
fi
ARGS+=("$@")

echo "microduck-skill: uv run play ${ARGS[*]}  (cwd=$RL_ROOT)"
echo "microduck-skill: Viser is a local webpage (not Hugging Face). --video writes logs/.../videos/play/"
uv run play "${ARGS[@]}"
echo "microduck-skill: play ok"
