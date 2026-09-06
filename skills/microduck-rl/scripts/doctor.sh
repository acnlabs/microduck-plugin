#!/usr/bin/env bash
# Ready-check. Optional: clone microduck_rl and uv sync.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

CLONE=0
CLONE_DIR=""
SYNC=0

usage() {
  cat <<'EOF'
usage: doctor.sh [--clone [DIR]] [--sync]

  --clone [DIR]  git clone pollen-robotics/microduck_rl
                 DIR defaults to $MICRODUCK_RL_ROOT or ~/.local/src/microduck_rl
  --sync         uv sync in the checkout (sets UV_HTTP_TIMEOUT=600)

Prints a checklist. Exits 1 if required tools or Jobs env are missing
(when not MICRODUCK_TRAIN_LOCAL=1).
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --clone)
      CLONE=1
      if [ -n "${2:-}" ] && [ "${2#-}" = "$2" ]; then
        CLONE_DIR="$2"
        shift 2
      else
        shift
      fi
      ;;
    --sync) SYNC=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown arg: $1" ;;
  esac
done

DEFAULT_RL="${MICRODUCK_RL_ROOT:-$HOME/.local/src/microduck_rl}"
fail=0
note() { echo "microduck-rl: $*"; }

if [ "$CLONE" -eq 1 ]; then
  require_cmd git
  dest="${CLONE_DIR:-$DEFAULT_RL}"
  if is_rl_checkout "$dest"; then
    note "already a checkout: $dest"
  elif [ -e "$dest" ] && [ ! -d "$dest/.git" ]; then
    die "refusing to clone over existing path: $dest"
  elif [ -d "$dest/.git" ]; then
    note "git repo exists but is not microduck_rl (no src/mjlab_microduck): $dest"
    fail=1
  else
    mkdir -p "$(dirname "$dest")"
    git clone https://github.com/pollen-robotics/microduck_rl "$dest"
    note "cloned $dest"
  fi
  export MICRODUCK_RL_ROOT="$dest"
fi

note "uv: $(command -v uv || echo MISSING)"
command -v uv >/dev/null || fail=1
note "python3: $(command -v python3 || echo MISSING)"
command -v python3 >/dev/null || fail=1

if [ -n "${MICRODUCK_RL_ROOT:-}" ] && is_rl_checkout "$MICRODUCK_RL_ROOT"; then
  note "MICRODUCK_RL_ROOT=$MICRODUCK_RL_ROOT (ok)"
  RL_ROOT="$(cd "$MICRODUCK_RL_ROOT" && pwd)"
elif is_rl_checkout "$PWD"; then
  note "cwd is a microduck_rl checkout: $PWD"
  RL_ROOT="$PWD"
elif is_rl_checkout "$DEFAULT_RL"; then
  note "found $DEFAULT_RL — export MICRODUCK_RL_ROOT=$DEFAULT_RL"
  RL_ROOT="$DEFAULT_RL"
else
  note "no microduck_rl checkout. Run: $0 --clone --sync"
  fail=1
  RL_ROOT=""
fi

if [ -n "$RL_ROOT" ] && [ "$SYNC" -eq 1 ]; then
  require_cmd uv
  note "uv sync in $RL_ROOT (UV_HTTP_TIMEOUT=${UV_HTTP_TIMEOUT:-600})"
  (
    cd "$RL_ROOT"
    export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-600}"
    uv sync
  )
fi

if jobs_mode; then
  if [ -n "${HF_TOKEN:-}" ] || [ -n "${HUGGING_FACE_HUB_TOKEN:-}" ] \
    || [ -f "${HF_HOME:-$HOME/.cache/huggingface}/token" ] \
    || [ -f "$HOME/.huggingface/token" ]; then
    note "HF auth: ok"
  else
    note "HF auth: MISSING (export HF_TOKEN or hf auth login)"
    fail=1
  fi
  if [ -n "${MICRODUCK_HF_NAMESPACE:-}" ]; then
    note "MICRODUCK_HF_NAMESPACE=$MICRODUCK_HF_NAMESPACE (ok)"
  else
    note "MICRODUCK_HF_NAMESPACE: MISSING (required for Jobs; interactive prompt hangs agents)"
    fail=1
  fi
  note "compute: Hugging Face Jobs (default). Local CUDA: MICRODUCK_TRAIN_LOCAL=1"
else
  note "compute: local (MICRODUCK_TRAIN_LOCAL=1)"
  if command -v nvidia-smi >/dev/null 2>&1; then
    note "nvidia-smi: present"
  else
    note "nvidia-smi: not found — local mjlab train will fail without CUDA"
    fail=1
  fi
fi

[ -n "${WANDB_API_KEY:-}" ] && note "WANDB_API_KEY: set" || note "WANDB_API_KEY: unset (optional; Jobs can forward it)"

note "invoke scripts with an absolute path, e.g."
note "  $SCRIPT_DIR/smoke.sh <TASK_ID>"

if [ "$fail" -ne 0 ]; then
  note "doctor failed"
  exit 1
fi
note "doctor ok"
echo "export MICRODUCK_RL_ROOT=${RL_ROOT:-$DEFAULT_RL}"
