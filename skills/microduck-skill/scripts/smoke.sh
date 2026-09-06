#!/usr/bin/env bash
# 64 envs × 5 iters. Same compute switch as train.sh (default: HF Jobs).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

TASK_ID="${1:-}"
[ -n "$TASK_ID" ] || die "usage: smoke.sh <TASK_ID>"

require_cmd uv
resolve_rl_root
cd "$RL_ROOT"

ARGS=("$TASK_ID" --env.scene.num-envs 64 --agent.max_iterations 5)
if jobs_mode; then
  require_jobs_ready
  set_jobs_extra
  ARGS+=("${JOBS_EXTRA[@]}")
  echo "microduck-skill: smoke $TASK_ID on Hugging Face Jobs (namespace=$MICRODUCK_HF_NAMESPACE)"
else
  echo "microduck-skill: smoke $TASK_ID locally (MICRODUCK_TRAIN_LOCAL=1)"
fi

echo "microduck-skill: uv run train ${ARGS[*]}  (cwd=$RL_ROOT)"
uv run train "${ARGS[@]}"
echo "microduck-skill: smoke ok"
