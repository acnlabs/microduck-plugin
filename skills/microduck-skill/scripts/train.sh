#!/usr/bin/env bash
# Default: Hugging Face Jobs. MICRODUCK_TRAIN_LOCAL=1 uses a local CUDA GPU.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

TASK_ID="${1:-}"
[ -n "$TASK_ID" ] || die "usage: train.sh <TASK_ID> [uv run train args…]"
shift

require_cmd uv
resolve_rl_root
cd "$RL_ROOT"

ARGS=("$TASK_ID")
if ! wandb_ready; then
  ARGS+=(--agent.logger tensorboard)
fi
if jobs_mode; then
  require_jobs_ready
  set_jobs_extra
  ARGS+=("${JOBS_EXTRA[@]}")
  echo "microduck-skill: Hugging Face Jobs train $TASK_ID (namespace=$MICRODUCK_HF_NAMESPACE)"
else
  echo "microduck-skill: local train (MICRODUCK_TRAIN_LOCAL=1)"
fi

if ! caller_set_num_envs "$@"; then
  ARGS+=(--env.scene.num-envs 4096)
fi

ARGS+=("$@")
echo "microduck-skill: uv run train ${ARGS[*]}  (cwd=$RL_ROOT)"
uv run train "${ARGS[@]}"
