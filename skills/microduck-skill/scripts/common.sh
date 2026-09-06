# Shared by smoke.sh / train.sh / export_publish.sh / doctor.sh. Source only.

die() {
  echo "microduck-skill: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

is_rl_checkout() {
  [ -f "$1/pyproject.toml" ] && [ -d "$1/src/mjlab_microduck" ]
}

resolve_rl_root() {
  if [ -n "${MICRODUCK_RL_ROOT:-}" ]; then
    RL_ROOT="$MICRODUCK_RL_ROOT"
  elif is_rl_checkout "$PWD"; then
    RL_ROOT="$PWD"
  else
    die "set MICRODUCK_RL_ROOT to a pollen-robotics/microduck_rl checkout (run scripts/doctor.sh --clone)"
  fi
  [ -d "$RL_ROOT" ] || die "cannot cd to $RL_ROOT"
  RL_ROOT="$(cd "$RL_ROOT" && pwd)"
  is_rl_checkout "$RL_ROOT" || die "not a microduck_rl checkout (need src/mjlab_microduck): $RL_ROOT"
}

require_hf_token() {
  if [ -n "${HF_TOKEN:-}" ] || [ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]; then
    return 0
  fi
  if [ -f "${HF_HOME:-$HOME/.cache/huggingface}/token" ] || [ -f "$HOME/.huggingface/token" ]; then
    return 0
  fi
  die "HF_TOKEN (or hf auth login) is required"
}

jobs_mode() {
  [ "${MICRODUCK_TRAIN_LOCAL:-}" != "1" ]
}

require_jobs_ready() {
  require_hf_token
  [ -n "${MICRODUCK_HF_NAMESPACE:-}" ] || die \
    "set MICRODUCK_HF_NAMESPACE to your HF user or org. Without it, Jobs prompts interactively and hangs an agent."
}

# Sets JOBS_EXTRA. Call after require_jobs_ready. Bash 3 compatible (no nameref).
wandb_ready() {
  [ -n "${WANDB_API_KEY:-}" ] && return 0
  [ -f "$HOME/.netrc" ] && grep -q wandb.ai "$HOME/.netrc" && return 0
  return 1
}

set_jobs_extra() {
  JOBS_EXTRA=(--hf-jobs --namespace "$MICRODUCK_HF_NAMESPACE")
  if [ -n "${MICRODUCK_HF_FLAVOR:-}" ]; then
    JOBS_EXTRA+=(--flavor "$MICRODUCK_HF_FLAVOR")
  fi
  if [ -n "${MICRODUCK_HF_TIMEOUT:-}" ]; then
    JOBS_EXTRA+=(--timeout "$MICRODUCK_HF_TIMEOUT")
  fi
  if ! wandb_ready; then
    JOBS_EXTRA+=(--no-wandb)
  fi
}

caller_set_num_envs() {
  local a
  for a in "$@"; do
    case "$a" in
      --env.scene.num-envs|*.num-envs|--env.scene.num-envs=*) return 0 ;;
    esac
  done
  return 1
}
