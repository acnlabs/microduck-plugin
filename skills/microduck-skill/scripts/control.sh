#!/usr/bin/env bash
# Localhost ONNX control for a simulated Microduck. Not Jobs. Not robotctl.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
usage:
  control.sh start --onnx PATH | --repo USER/NAME [--standing|--sitstand|--sit|--slope|--ground-pick|--kick-left|--kick-right|--roulade FILE] ...
  control.sh pull USER/NAME [--as walk|standing|sitstand|sit|slope|ground_pick|kick_left|kick_right|roulade]
  control.sh twist [--x M] [--y M] [--yaw RAD]
  control.sh head [--neck RAD] [--pitch RAD] [--yaw RAD] [--roll RAD] [--reset]
  control.sh body [--x M] [--y M] [--z M] [--roll RAD] [--pitch RAD] [--yaw RAD] [--reset]
  control.sh sit [--off]
  control.sh stand
  control.sh do sit|stand|kick_left|kick_right|roulade|ground_pick|slope
  control.sh stop
  control.sh status
  control.sh shutdown

--repo / pull fetch Hub policy.onnx (gated 61→14). --as copies extras into
.microduck-plugin-skills/. Sit/kick/roll/pick stay valid verbs (loaded|untrained).
HTTP is localhost only. play.sh is still the Viser checkpoint viewer.
EOF
}

CMD="${1:-}"
[ -n "$CMD" ] || { usage; die "usage: control.sh start|pull|twist|head|body|sit|stand|do|stop|status|shutdown"; }
shift || true

STATE_NAME=".microduck-plugin-control.json"

state_path() {
  resolve_rl_root
  echo "$RL_ROOT/$STATE_NAME"
}

read_url() {
  local st
  st="$(state_path)"
  [ -f "$st" ] || die "control server is not running (no $STATE_NAME). Start with: control.sh start --onnx FILE"
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["url"])' "$st"
}

http() {
  local method="$1" path="$2" body="${3:-}"
  local url
  url="$(read_url)"
  python3 - "$method" "$url$path" "$body" <<'PY'
import sys, urllib.error, urllib.request
method, url, body = sys.argv[1], sys.argv[2], sys.argv[3]
data = body.encode() if body else None
headers = {"Content-Type": "application/json"} if data else {}
req = urllib.request.Request(url, data=data, method=method, headers=headers)
try:
    print(urllib.request.urlopen(req, timeout=5).read().decode())
except urllib.error.HTTPError as exc:
    print(exc.read().decode() or str(exc))
    raise SystemExit(1)
PY
}

abs_file() {
  local p="$1"
  [ -n "$p" ] || return 0
  [ -f "$p" ] || die "not a file: $p"
  echo "$(cd "$(dirname "$p")" && pwd)/$(basename "$p")"
}

first_existing() {
  local f
  for f in "$@"; do
    if [ -f "$f" ]; then
      echo "$f"
      return 0
    fi
  done
  return 1
}

gate_onnx() {
  local f="$1" label="$2"
  echo "microduck-skill: gate $label $f"
  uv run --with onnx python3 "$SCRIPT_DIR/gate_check.py" "$f" >/dev/null
  echo "microduck-skill: gate ok $label"
}

hub_fetch() {
  local repo="$1" dest slug py
  case "$repo" in
    */*) ;;
    *) die "repo must be USER/NAME (got $repo)" ;;
  esac
  slug=$(printf '%s' "$repo" | tr '/' '-')
  dest="$RL_ROOT/.microduck-plugin-hub/$slug"
  mkdir -p "$dest"
  echo "microduck-skill: hub pull $repo" >&2
  py="$RL_ROOT/.venv/bin/python"
  if [ -x "$py" ]; then
    "$py" "$SCRIPT_DIR/hub_pull.py" "$repo" --out "$dest"
  else
    uv run --with huggingface_hub python3 "$SCRIPT_DIR/hub_pull.py" "$repo" --out "$dest"
  fi
}

case "$CMD" in
  start)
    ONNX=""
    REPO=""
    STANDING="" SITSTAND="" SIT="" SLOPE="" PICK="" KICK_L="" KICK_R="" ROULADE=""
    BIND="${MICRODUCK_CONTROL_BIND:-127.0.0.1:8765}"
    DETACH=0
    VIEWER=0
    RECORD=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --onnx) ONNX="${2:-}"; shift 2 ;;
        --repo) REPO="${2:-}"; shift 2 ;;
        --standing) STANDING="${2:-}"; shift 2 ;;
        --sitstand) SITSTAND="${2:-}"; shift 2 ;;
        --sit) SIT="${2:-}"; shift 2 ;;
        --slope) SLOPE="${2:-}"; shift 2 ;;
        --ground-pick) PICK="${2:-}"; shift 2 ;;
        --kick-left) KICK_L="${2:-}"; shift 2 ;;
        --kick-right) KICK_R="${2:-}"; shift 2 ;;
        --roulade) ROULADE="${2:-}"; shift 2 ;;
        --bind) BIND="${2:-}"; shift 2 ;;
        --detach) DETACH=1; shift ;;
        --viewer) VIEWER=1; shift ;;
        --record) RECORD="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown start arg: $1" ;;
      esac
    done
    if [ -n "$ONNX" ] && [ -n "$REPO" ]; then
      die "use --onnx or --repo, not both"
    fi
    [ -n "$ONNX" ] || [ -n "$REPO" ] || die "start requires --onnx PATH or --repo USER/NAME"
    require_cmd uv
    require_cmd python3
    resolve_rl_root
    if [ -n "$REPO" ]; then
      ONNX="$(hub_fetch "$REPO")"
      echo "microduck-skill: if you own a duck: sudo robotctl policy load walk $REPO"
    fi
    [ -f "$ONNX" ] || die "policy is not a file: $ONNX"
    SKILLS_DIR="${MICRODUCK_SKILLS_DIR:-$RL_ROOT/.microduck-plugin-skills}"
    if [ -z "$STANDING" ]; then STANDING="$(first_existing "$SKILLS_DIR/standing.onnx" || true)"; fi
    if [ -z "$SITSTAND" ]; then SITSTAND="$(first_existing "$SKILLS_DIR/sitstand.onnx" "$SKILLS_DIR/BEST_alpha_sitstand.onnx" || true)"; fi
    if [ -z "$SIT" ]; then SIT="$(first_existing "$SKILLS_DIR/sit.onnx" || true)"; fi
    if [ -z "$SLOPE" ]; then SLOPE="$(first_existing "$SKILLS_DIR/slope.onnx" || true)"; fi
    if [ -z "$PICK" ]; then PICK="$(first_existing "$SKILLS_DIR/ground_pick.onnx" "$SKILLS_DIR/ground-pick.onnx" || true)"; fi
    if [ -z "$KICK_L" ]; then KICK_L="$(first_existing "$SKILLS_DIR/kick_left.onnx" "$SKILLS_DIR/ball_kick_left.onnx" || true)"; fi
    if [ -z "$KICK_R" ]; then KICK_R="$(first_existing "$SKILLS_DIR/kick_right.onnx" "$SKILLS_DIR/ball_kick_right.onnx" || true)"; fi
    if [ -z "$ROULADE" ]; then ROULADE="$(first_existing "$SKILLS_DIR/roulade.onnx" || true)"; fi
    if [ -n "$SITSTAND" ] && [ -n "$SIT" ]; then
      echo "microduck-skill: both sitstand and sit found; using sitstand" >&2
      SIT=""
    fi
    ONNX="$(abs_file "$ONNX")"
    STANDING="$(abs_file "$STANDING")"
    SITSTAND="$(abs_file "$SITSTAND")"
    SIT="$(abs_file "$SIT")"
    SLOPE="$(abs_file "$SLOPE")"
    PICK="$(abs_file "$PICK")"
    KICK_L="$(abs_file "$KICK_L")"
    KICK_R="$(abs_file "$KICK_R")"
    ROULADE="$(abs_file "$ROULADE")"
    gate_onnx "$ONNX" walk
    [ -n "$STANDING" ] && gate_onnx "$STANDING" standing
    [ -n "$SITSTAND" ] && gate_onnx "$SITSTAND" sitstand
    [ -n "$SIT" ] && gate_onnx "$SIT" sit
    [ -n "$SLOPE" ] && gate_onnx "$SLOPE" slope
    [ -n "$PICK" ] && gate_onnx "$PICK" ground_pick
    [ -n "$KICK_L" ] && gate_onnx "$KICK_L" kick_left
    [ -n "$KICK_R" ] && gate_onnx "$KICK_R" kick_right
    [ -n "$ROULADE" ] && gate_onnx "$ROULADE" roulade

    PY=("$RL_ROOT/.venv/bin/python")
    if [ ! -x "${PY[0]}" ]; then
      PY=(uv run python)
    fi
    if [ "$VIEWER" -eq 1 ] && [ "$(uname -s)" = "Darwin" ] && [ -x "$RL_ROOT/.venv/bin/mjpython" ]; then
      PY=("$RL_ROOT/.venv/bin/mjpython")
      if [ -d "$HOME/.local/share/uv/python" ]; then
        LIBPY="$(echo "$HOME"/.local/share/uv/python/cpython-3.12.*/lib | awk '{print $1}')"
        if [ -d "$LIBPY" ]; then
          export DYLD_LIBRARY_PATH="$LIBPY${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
        fi
      fi
    fi

    ARGS=(--onnx "$ONNX" --rl-root "$RL_ROOT" --bind "$BIND")
    [ -n "$STANDING" ] && ARGS+=(--standing "$STANDING")
    [ -n "$SITSTAND" ] && ARGS+=(--sitstand "$SITSTAND")
    [ -n "$SIT" ] && ARGS+=(--sit "$SIT")
    [ -n "$SLOPE" ] && ARGS+=(--slope "$SLOPE")
    [ -n "$PICK" ] && ARGS+=(--ground-pick "$PICK")
    [ -n "$KICK_L" ] && ARGS+=(--kick-left "$KICK_L")
    [ -n "$KICK_R" ] && ARGS+=(--kick-right "$KICK_R")
    [ -n "$ROULADE" ] && ARGS+=(--roulade "$ROULADE")
    [ "$VIEWER" -eq 1 ] && ARGS+=(--viewer)
    [ -n "$RECORD" ] && ARGS+=(--record "$RECORD")

    HOSTPORT="$BIND"
    case "$HOSTPORT" in
      *:*) ;;
      *) HOSTPORT="127.0.0.1:$HOSTPORT" ;;
    esac
    URL="http://$HOSTPORT"
    ST="$RL_ROOT/$STATE_NAME"
    if [ -f "$ST" ]; then
      if python3 - "$ST" <<'PY' >/dev/null 2>&1
import json, sys, urllib.request
url = json.load(open(sys.argv[1]))["url"]
urllib.request.urlopen(url + "/status", timeout=1).read()
PY
      then
        die "control already running at $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["url"])' "$ST")"
      fi
      rm -f "$ST"
    fi

    echo "microduck-skill: control start $URL  (cwd=$RL_ROOT)"
    cd "$RL_ROOT"
    if [ "$DETACH" -eq 1 ]; then
      nohup "${PY[@]}" "$SCRIPT_DIR/control_server.py" "${ARGS[@]}" >"$RL_ROOT/.microduck-plugin-control.log" 2>&1 &
      echo "{\"pid\": $!, \"url\": \"$URL\", \"onnx\": \"$ONNX\"}" >"$ST"
      echo "microduck-skill: detached pid $!  log=$RL_ROOT/.microduck-plugin-control.log"
      i=0
      while [ "$i" -lt 45 ]; do
        if python3 - "$URL" <<'PY' >/dev/null 2>&1
import sys, urllib.request
urllib.request.urlopen(sys.argv[1] + "/status", timeout=1).read()
PY
        then
          echo "microduck-skill: control ready $URL"
          exit 0
        fi
        i=$((i + 1))
        sleep 1
      done
      die "control did not become ready in 45s; see $RL_ROOT/.microduck-plugin-control.log"
    else
      echo "{\"pid\": $$, \"url\": \"$URL\", \"onnx\": \"$ONNX\"}" >"$ST"
      exec "${PY[@]}" "$SCRIPT_DIR/control_server.py" "${ARGS[@]}"
    fi
    ;;
  pull)
    REPO="${1:-}"
    [ -n "$REPO" ] || die "pull requires USER/NAME"
    shift || true
    AS="walk"
    while [ $# -gt 0 ]; do
      case "$1" in
        --as) AS="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown pull arg: $1" ;;
      esac
    done
    case "$AS" in
      walk|standing|sitstand|sit|slope|ground_pick|kick_left|kick_right|roulade) ;;
      *) die "unknown --as $AS (walk|standing|sitstand|sit|slope|ground_pick|kick_left|kick_right|roulade)" ;;
    esac
    require_cmd uv
    require_cmd python3
    resolve_rl_root
    ONNX="$(hub_fetch "$REPO")"
    [ -f "$ONNX" ] || die "hub pull produced no file"
    gate_onnx "$ONNX" "$AS"
    if [ "$AS" != "walk" ]; then
      SKILLS_DIR="${MICRODUCK_SKILLS_DIR:-$RL_ROOT/.microduck-plugin-skills}"
      mkdir -p "$SKILLS_DIR"
      cp "$ONNX" "$SKILLS_DIR/${AS}.onnx"
      echo "microduck-skill: installed $AS -> $SKILLS_DIR/${AS}.onnx"
    fi
    echo "microduck-skill: pulled $REPO ($AS) $ONNX"
    echo "microduck-skill: if you own a duck: sudo robotctl policy add $AS $REPO"
    ;;
  twist)
    X=0 Y=0 YAW=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --x) X="${2:-}"; shift 2 ;;
        --y) Y="${2:-}"; shift 2 ;;
        --yaw) YAW="${2:-}"; shift 2 ;;
        *) die "unknown twist arg: $1" ;;
      esac
    done
    http POST /twist "{\"x\": $X, \"y\": $Y, \"yaw\": $YAW}"
    ;;
  head)
    RESET=0
    NECK="" PITCH="" YAW="" ROLL=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --neck) NECK="${2:-}"; shift 2 ;;
        --pitch) PITCH="${2:-}"; shift 2 ;;
        --yaw) YAW="${2:-}"; shift 2 ;;
        --roll) ROLL="${2:-}"; shift 2 ;;
        --reset) RESET=1; shift ;;
        *) die "unknown head arg: $1" ;;
      esac
    done
    BODY="$(NECK="$NECK" PITCH="$PITCH" YAW="$YAW" ROLL="$ROLL" RESET="$RESET" python3 - <<'PY'
import json, os
if os.environ["RESET"] == "1":
    print(json.dumps({"reset": True}))
else:
    d = {}
    for key, env in (
        ("neck_pitch", "NECK"),
        ("head_pitch", "PITCH"),
        ("head_yaw", "YAW"),
        ("head_roll", "ROLL"),
    ):
        raw = os.environ.get(env, "")
        if raw != "":
            d[key] = float(raw)
    if not d:
        raise SystemExit("head: pass --reset or at least one of --neck --pitch --yaw --roll")
    print(json.dumps(d))
PY
)"
    http POST /head "$BODY"
    ;;
  body)
    RESET=0
    BX="" BY="" BZ="" BROLL="" BPITCH="" BYAW=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --x) BX="${2:-}"; shift 2 ;;
        --y) BY="${2:-}"; shift 2 ;;
        --z) BZ="${2:-}"; shift 2 ;;
        --roll) BROLL="${2:-}"; shift 2 ;;
        --pitch) BPITCH="${2:-}"; shift 2 ;;
        --yaw) BYAW="${2:-}"; shift 2 ;;
        --reset) RESET=1; shift ;;
        *) die "unknown body arg: $1" ;;
      esac
    done
    BODY="$(BX="$BX" BY="$BY" BZ="$BZ" BROLL="$BROLL" BPITCH="$BPITCH" BYAW="$BYAW" RESET="$RESET" python3 - <<'PY'
import json, os
if os.environ["RESET"] == "1":
    print(json.dumps({"reset": True}))
else:
    d = {}
    for key, env in (
        ("x", "BX"),
        ("y", "BY"),
        ("z", "BZ"),
        ("roll", "BROLL"),
        ("pitch", "BPITCH"),
        ("yaw", "BYAW"),
    ):
        raw = os.environ.get(env, "")
        if raw != "":
            d[key] = float(raw)
    if not d:
        raise SystemExit("body: pass --reset or at least one of --x --y --z --roll --pitch --yaw")
    print(json.dumps(d))
PY
)"
    http POST /body "$BODY"
    ;;
  sit)
    ON=true
    while [ $# -gt 0 ]; do
      case "$1" in
        --off) ON=false; shift ;;
        *) die "unknown sit arg: $1" ;;
      esac
    done
    http POST /sit "{\"on\": $ON}"
    ;;
  stand) http POST /stand "{}" ;;
  do)
    SKILL_NAME="${1:-}"
    [ -n "$SKILL_NAME" ] || die "do requires a skill: sit|stand|kick_left|kick_right|roulade|ground_pick|slope"
    http POST /do "{\"skill\": \"$SKILL_NAME\"}"
    ;;
  stop) http POST /stop "{}" ;;
  status) http GET /status ;;
  shutdown)
    http POST /shutdown "{}" || true
    st="$(state_path)"
    if [ -f "$st" ]; then
      pid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("pid",""))' "$st" 2>/dev/null || true)"
      [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
      rm -f "$st"
    fi
    echo "microduck-skill: control shutdown"
    ;;
  -h|--help) usage; exit 0 ;;
  *) usage; die "unknown command: $CMD" ;;
esac
