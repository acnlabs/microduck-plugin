#!/usr/bin/env bash
# Official export (normalizer baked in) + Hub publish. No robotctl. No ONNX search.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

TASK=""
WANDB=""
CHECKPOINT=""
CHECKPOINT_FILE=""
REPO=""
KIND=""
DURATION=""
UNWIND=""
SLOT=""
DESCRIPTION=""
ONNX=""
CHAIN=0
EXTRA=()

usage() {
  cat <<'EOF'
usage: export_publish.sh --repo USER/microduck-NAME --kind episodic|perpetual [source] [options]

source (exactly one export path):
  --task TASK_ID --wandb-run-path ENT/PROJ/RUN
  --task TASK_ID --checkpoint-file /path/model_N.pt
  --onnx FILE             skip export; gate + publish this file only

options:
  --checkpoint N          wandb iteration (model_N.pt)
  --duration-s SEC        required for episodic
  --unwind-s SEC          perpetual held pose
  --slot walk|stand       perpetual gait slot
  --description TEXT
  --chain                 episodic repeat-on-hold
  extra args are forwarded to `uv run publish`
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --task) TASK="${2:-}"; shift 2 ;;
    --wandb-run-path) WANDB="${2:-}"; shift 2 ;;
    --checkpoint) CHECKPOINT="${2:-}"; shift 2 ;;
    --checkpoint-file) CHECKPOINT_FILE="${2:-}"; shift 2 ;;
    --repo) REPO="${2:-}"; shift 2 ;;
    --kind) KIND="${2:-}"; shift 2 ;;
    --duration-s) DURATION="${2:-}"; shift 2 ;;
    --unwind-s) UNWIND="${2:-}"; shift 2 ;;
    --slot) SLOT="${2:-}"; shift 2 ;;
    --description) DESCRIPTION="${2:-}"; shift 2 ;;
    --onnx) ONNX="${2:-}"; shift 2 ;;
    --chain) CHAIN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

[ -n "$REPO" ] || die "missing --repo"
[ -n "$KIND" ] || die "missing --kind"
case "$KIND" in
  episodic|perpetual) ;;
  *) die "--kind must be episodic or perpetual (phase/posture-flag are not community-publishable)" ;;
esac
if [ "$KIND" = "episodic" ] && [ -z "$DURATION" ]; then
  die "episodic requires --duration-s"
fi

require_cmd uv
require_cmd python3
require_hf_token
resolve_rl_root
cd "$RL_ROOT"

if [ -z "$ONNX" ]; then
  [ -n "$TASK" ] || die "missing --task (or pass --onnx)"
  if [ -z "$WANDB" ] && [ -z "$CHECKPOINT_FILE" ]; then
    die "missing --wandb-run-path or --checkpoint-file (or pass --onnx)"
  fi
  ONNX="$RL_ROOT/.microduck-plugin-export.onnx"
  EXPORT=("$TASK" --onnx-file "$ONNX")
  [ -n "$WANDB" ] && EXPORT+=(--wandb-run-path "$WANDB")
  [ -n "$CHECKPOINT" ] && EXPORT+=(--checkpoint "$CHECKPOINT")
  [ -n "$CHECKPOINT_FILE" ] && EXPORT+=(--checkpoint-file "$CHECKPOINT_FILE")
  echo "microduck-skill: export ${EXPORT[*]}"
  uv run scripts/export.py "${EXPORT[@]}"
  [ -f "$ONNX" ] || die "export did not write $ONNX (refusing to search the tree)"
else
  [ -f "$ONNX" ] || die "--onnx is not a file: $ONNX"
fi

echo "microduck-skill: gate $ONNX"
run_gate_check "$SCRIPT_DIR/gate_check.py" "$ONNX"

# Upstream publish refuses --onnx plus --task/--wandb-run-path. Weights are
# already an official ONNX; only manifest flags go to publish.
PUB=(publish --onnx "$ONNX" --repo "$REPO" --kind "$KIND")
[ -n "$DURATION" ] && PUB+=(--duration-s "$DURATION")
[ -n "$UNWIND" ] && PUB+=(--unwind-s "$UNWIND")
[ -n "$SLOT" ] && PUB+=(--slot "$SLOT")
[ -n "$DESCRIPTION" ] && PUB+=(--description "$DESCRIPTION")
[ "$CHAIN" -eq 1 ] && PUB+=(--chain)
if [ "${#EXTRA[@]}" -gt 0 ]; then
  PUB+=("${EXTRA[@]}")
fi

echo "microduck-skill: uv run ${PUB[*]}"
uv run "${PUB[@]}"

echo
echo "microduck-skill: published $REPO"
echo "Print, do not run, unless the user asked to install on a real robot:"
case "$KIND" in
  episodic)
    echo "  sudo robotctl policy add <name> $REPO"
    echo "  robotctl robot do <name>"
    ;;
  perpetual)
    if [ -n "$SLOT" ]; then
      echo "  sudo robotctl policy load $SLOT $REPO"
    else
      echo "  sudo robotctl policy add <name> $REPO --hold <seconds>"
    fi
    ;;
esac
