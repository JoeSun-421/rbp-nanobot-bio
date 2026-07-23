#!/usr/bin/env bash
# =============================================================================
# nanobot-bio — sole environment setup entry (Linux / SSH)
# =============================================================================
# First-time (science conda + agent + optional AF3 hardening):
#   bash scripts/setup_all.sh
#
# Day-to-day (standard venv; CLI loads .env automatically):
#   source $BIO_ROOT/nanobot-bio/.venv/bin/activate
#   rbp-agent doctor && rbp-agent chat
#
# Options:
#   --skip-conda     agent venv only (no RhoBind/ESM/AF3)
#   --skip-smoke     skip doctor smoke check
#   --skip-af3       skip AF3 hardening (default on; 10-minute budget)
#   AF3_BUDGET_SEC=600  AF3 hardening timeout (then deferred)
#
# Does not modify rhobind_agent_delivery sources; read-only use of setup_envs / tools.
# =============================================================================
set -euo pipefail

WITH_CONDA=1
SKIP_SMOKE=0
SKIP_AF3=0
for arg in "$@"; do
  case "$arg" in
    --with-conda) WITH_CONDA=1 ;;
    --skip-conda) WITH_CONDA=0 ;;
    --skip-smoke) SKIP_SMOKE=1 ;;
    --skip-af3) SKIP_AF3=1 ;;
    -h|--help) sed -n '1,25p' "$0"; exit 0 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIO_ROOT="$(cd "${BIO_ROOT:-$AGENT_ROOT/..}" && pwd)"
DELIVERY_ROOT="${DELIVERY_ROOT:-$BIO_ROOT/rhobind_agent_delivery}"
NANOBOT_SRC="${NANOBOT_SRC:-$BIO_ROOT/nanobot}"
export BIO_ROOT NANOBOT_SRC DELIVERY_ROOT
export NANOBOT_BIO_ROOT="$AGENT_ROOT"
export NANOBOT_WORKSPACE="$AGENT_ROOT/workspace"

# ---------------------------------------------------------------------------
# Inline: ensure sibling nanobot runtime (clone HKUDS/nanobot if missing)
# ---------------------------------------------------------------------------
_ensure_nanobot() {
  local NANOBOT_GIT_DEFAULT="https://github.com/HKUDS/nanobot.git"
  local NANOBOT_GIT="${NANOBOT_GIT:-$NANOBOT_GIT_DEFAULT}"
  local NANOBOT_CLONE_TIMEOUT="${NANOBOT_CLONE_TIMEOUT:-180}"
  NANOBOT_SRC="${NANOBOT_SRC:-$BIO_ROOT/nanobot}"

  case "$NANOBOT_SRC" in
    *"nanobot-bio/nanobot"|*"nanobot-bio/nanobot/")
      if [[ ! -f "$NANOBOT_SRC/nanobot.py" && ! -f "$NANOBOT_SRC/pyproject.toml" ]]; then
        NANOBOT_SRC="$BIO_ROOT/nanobot"
      fi
      ;;
  esac

  _nanobot_ok() {
    local d="$1"
    [[ -f "$d/__init__.py" || -f "$d/nanobot.py" || -f "$d/pyproject.toml" ]]
  }

  if _nanobot_ok "$NANOBOT_SRC"; then
    echo "[ensure_nanobot] OK: $NANOBOT_SRC"
    export NANOBOT_SRC
    return 0
  fi

  if [[ "${NANOBOT_NO_CLONE:-0}" == "1" ]]; then
    echo "ERROR: nanobot runtime missing at $NANOBOT_SRC (NANOBOT_NO_CLONE=1)" >&2
    return 1
  fi
  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git required to clone nanobot into $NANOBOT_SRC" >&2
    return 1
  fi

  if [[ -e "$NANOBOT_SRC" ]]; then
    if [[ -d "$NANOBOT_SRC" ]] && [[ -z "$(ls -A "$NANOBOT_SRC" 2>/dev/null || true)" ]]; then
      rmdir "$NANOBOT_SRC" 2>/dev/null || true
    elif [[ -d "$NANOBOT_SRC" ]] && ! _nanobot_ok "$NANOBOT_SRC"; then
      if [[ -d "$NANOBOT_SRC/skills/rbp-agent" || -d "$NANOBOT_SRC/agent/tools/rbp" ]]; then
        echo "ERROR: $NANOBOT_SRC looks like a plugin overlay, not the nanobot runtime." >&2
        echo "  Set NANOBOT_SRC=\$BIO_ROOT/nanobot (sibling) and re-run." >&2
        return 1
      fi
      echo "WARN: incomplete nanobot at $NANOBOT_SRC — moving aside" >&2
      mv "$NANOBOT_SRC" "${NANOBOT_SRC}.bak.$(date +%s)"
    fi
  fi

  local _urls=()
  _urls+=("$NANOBOT_GIT")
  if [[ "$NANOBOT_GIT" == "$NANOBOT_GIT_DEFAULT" ]]; then
    _urls+=(
      "https://ghproxy.net/https://github.com/HKUDS/nanobot.git"
      "https://mirror.ghproxy.com/https://github.com/HKUDS/nanobot.git"
      "https://gitclone.com/github.com/HKUDS/nanobot.git"
    )
  fi

  mkdir -p "$(dirname "$NANOBOT_SRC")"
  local _cloned=0 _url _ok
  export GIT_TERMINAL_PROMPT=0
  for _url in "${_urls[@]}"; do
    echo "[ensure_nanobot] cloning (${NANOBOT_CLONE_TIMEOUT}s) $_url → $NANOBOT_SRC"
    rm -rf "$NANOBOT_SRC"
    _ok=0
    if command -v timeout >/dev/null 2>&1; then
      if timeout -k 8 "$NANOBOT_CLONE_TIMEOUT" \
        git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 \
        clone --depth 1 "$_url" "$NANOBOT_SRC"
      then
        _ok=1
      fi
    else
      if git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 \
        clone --depth 1 "$_url" "$NANOBOT_SRC"
      then
        _ok=1
      fi
    fi
    if [[ "$_ok" == "1" ]] && _nanobot_ok "$NANOBOT_SRC"; then
      _cloned=1
      break
    fi
    echo "[ensure_nanobot] WARN: clone failed/timeout for $_url" >&2
    rm -rf "$NANOBOT_SRC"
  done

  if [[ "$_cloned" != "1" ]] || ! _nanobot_ok "$NANOBOT_SRC"; then
    echo "ERROR: could not clone nanobot runtime into $NANOBOT_SRC" >&2
    echo "  Manual: git clone --depth 1 https://github.com/HKUDS/nanobot.git $NANOBOT_SRC" >&2
    return 1
  fi
  echo "[ensure_nanobot] cloned OK: $NANOBOT_SRC"
  export NANOBOT_SRC
  return 0
}

# ---------------------------------------------------------------------------
# Inline: AF3 harden (writes nanobot-bio/.af3_status only; delivery read-only)
# ---------------------------------------------------------------------------
_setup_af3() {
  local AF3_DIR="${AF3_DIR:-$DELIVERY_ROOT/agent/third_party/alphafold3}"
  local YML="$AF3_DIR/af3_env.yml"
  local PIP_INDEX="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
  local PIP_HOST="${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}"
  local AF3_BUDGET_SEC="${AF3_BUDGET_SEC:-600}"
  local STATUS_FILE="${AF3_STATUS_FILE:-$AGENT_ROOT/.af3_status}"
  local _START
  _START=$(date +%s)

  _budget_left() {
    local now elapsed
    now=$(date +%s)
    elapsed=$((now - _START))
    echo $((AF3_BUDGET_SEC - elapsed))
  }
  _stop_if_over() {
    local left
    left="$(_budget_left)"
    if (( left <= 0 )); then
      echo "[af3] BUDGET ${AF3_BUDGET_SEC}s exceeded — stop; resume tomorrow." >&2
      _write_status deferred "budget_exceeded"
      return 1
    fi
    return 0
  }
  _write_status() {
    local state="$1" note="${2:-}"
    {
      echo "state=$state"
      echo "ts=$(date -Iseconds 2>/dev/null || date)"
      echo "note=$note"
      echo "af3_python=${AF3_PYTHON:-}"
      echo "budget_sec=$AF3_BUDGET_SEC"
    } > "$STATUS_FILE"
    echo "[af3] wrote $STATUS_FILE ($state)"
  }

  echo "[af3] budget=${AF3_BUDGET_SEC}s  DELIVERY_ROOT=$DELIVERY_ROOT (read-only)"
  if [[ ! -f "$YML" ]]; then
    echo "ERROR: missing $YML" >&2
    _write_status missing "no_af3_env_yml"
    return 1
  fi
  command -v conda >/dev/null || { echo "ERROR: conda required" >&2; return 1; }

  _stop_if_over || return 0
  if ! conda env list 2>/dev/null | awk '{print $1}' | grep -qx af3; then
    echo "[af3] creating env via delivery setup_af3.sh ..."
    # shellcheck disable=SC1091
    source "$DELIVERY_ROOT/agent/setup.sh"
    timeout "$(_budget_left)" bash "$DELIVERY_ROOT/agent/setup_af3.sh" \
      || { _write_status deferred "setup_af3_timeout_or_fail"; return 0; }
  fi

  local AF3_PY
  AF3_PY="$(conda run -n af3 which python 2>/dev/null || true)"
  if [[ -z "$AF3_PY" || ! -x "$AF3_PY" ]]; then
    _write_status missing "no_af3_python"
    return 1
  fi
  export AF3_PYTHON="$AF3_PY"
  echo "[af3] AF3_PYTHON=$AF3_PYTHON"

  _stop_if_over || return 0
  echo "[af3] ensure jax/triton pins from af3_env.yml ..."
  local PINS=()
  mapfile -t PINS < <(python - <<PY
from pathlib import Path
pins, in_pip = [], False
for line in Path(r"$YML").read_text().splitlines():
    s = line.strip()
    if s.startswith("- pip:"):
        in_pip = True
        continue
    if in_pip:
        if s.startswith("- ") and "==" in s:
            pins.append(s[2:].strip())
        elif s and not s.startswith("-") and not s.startswith("#"):
            break
want = [p for p in pins if p.split("==")[0] in (
    "jax", "jaxlib", "triton", "jax-cuda12-pjrt", "jax-cuda12-plugin",
)]
for p in want:
    print(p)
PY
)
  if ((${#PINS[@]})); then
    timeout "$(_budget_left)" "$AF3_PY" -m pip install --no-deps \
      -i "$PIP_INDEX" --trusted-host "$PIP_HOST" "${PINS[@]}" -q \
      || true
  fi

  _stop_if_over || return 0
  echo "[af3] bump nvidia-cuda-nvcc-cu12 (≥12.8) for new GPUs ..."
  timeout "$(_budget_left)" "$AF3_PY" -m pip install -U 'nvidia-cuda-nvcc-cu12>=12.8' \
    -i "$PIP_INDEX" --trusted-host "$PIP_HOST" -q \
    || echo "[af3] WARN: nvcc bump skipped"

  _stop_if_over || return 0
  echo "[af3] import verify ..."
  if ! "$AF3_PY" - <<'PY'
import jax, triton
import alphafold3  # noqa: F401
print("jax", jax.__version__, "triton", triton.__version__, "devices", jax.devices())
# AF3 historically pinned jax 0.4.*; accept 0.4+ (0.5/0.6 stacks are deferred-capable).
_jv = tuple(int(x) for x in jax.__version__.split(".")[:2])
assert _jv >= (0, 4), jax.__version__
print("import OK")
PY
  then
    # Imports failed: prefer deferred (AFDB path still valid) over broken hard-stop.
    _write_status deferred "import_failed_use_afdb"
    return 0
  fi

  _stop_if_over || return 0
  if [[ "${AF3_SKIP_SMOKE:-0}" == "1" ]]; then
    _write_status import_ok "smoke_skipped"
  else
    echo "[af3] short inference smoke (remaining $(_budget_left)s) ..."
    export AF3_DIR AF3_PARAMS="${AF3_PARAMS:-$DELIVERY_ROOT/af3_assets/alphafold_param}"
    export AF3_CACHE="${AF3_CACHE:-/tmp/af3_cache}"
    mkdir -p "$AF3_CACHE"
    set +e
    timeout "$(_budget_left)" "$AF3_PY" \
      "$DELIVERY_ROOT/agent/tools/structure/structure_predict_af3.py" --json \
      '{"sequence":"MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG","name":"ubq"}' \
      > /tmp/af3_budget_smoke.out 2> /tmp/af3_budget_smoke.err
    local ec=$?
    set -e
    if grep -q '"ok": true' /tmp/af3_budget_smoke.out 2>/dev/null; then
      _write_status ok "smoke_passed"
    else
      local note="smoke_failed_ec=${ec}; Blackwell/Triton often needs newer jax — defer"
      echo "[af3] inference smoke failed (imports OK). $note"
      echo "[af3] Agent can still use AFDB via structure_fetch / struct_similarity."
      _write_status deferred "$note"
    fi
  fi

  local ENVF="$AGENT_ROOT/.env"
  if [[ -f "$ENVF" ]]; then
    if grep -q '^AF3_PYTHON=' "$ENVF"; then
      sed -i "s|^AF3_PYTHON=.*|AF3_PYTHON=$AF3_PYTHON|" "$ENVF"
    else
      echo "AF3_PYTHON=$AF3_PYTHON" >> "$ENVF"
    fi
  fi
  echo "[af3] done (elapsed $(( $(date +%s) - _START ))s)"
  return 0
}

# =============================================================================
_ensure_nanobot
NANOBOT_SRC="${NANOBOT_SRC}"
export NANOBOT_SRC

echo "=============================================="
echo " nanobot-bio setup (Linux / plugin overlay)"
echo "=============================================="
echo "  BIO_ROOT      = $BIO_ROOT"
echo "  AGENT_ROOT    = $AGENT_ROOT"
echo "  DELIVERY_ROOT = $DELIVERY_ROOT"
echo "  NANOBOT_SRC   = $NANOBOT_SRC"
echo "  OS            = $(uname -s)"
echo

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "WARNING: uname=$(uname -s). Official setup target is Linux SSH server." >&2
fi

if [[ ! -d "$DELIVERY_ROOT/agent" ]]; then
  echo "ERROR: delivery missing: $DELIVERY_ROOT" >&2
  exit 1
fi

echo "[1/6] apply delivery env (no AF3 conda probe)"
_bundle="$DELIVERY_ROOT"
export BUNDLE_ROOT="$_bundle"
export AGENT_DB="${AGENT_DB:-$_bundle/agent_db}"
export RBP_PROTEINS="${RBP_PROTEINS:-$_bundle/reference}"
export RHOBIND_RELEASE="${RHOBIND_RELEASE:-$_bundle/release/rhobind_release_v1}"
export USALIGN="${USALIGN:-$AGENT_DB/bin/USalign}"
export PEAKS_DB="${PEAKS_DB:-$AGENT_DB/peaks_db/peaks}"
export TRANSFER_DIR="${TRANSFER_DIR:-$AGENT_DB/transfer}"
export AFDB_DIR="${AFDB_DIR:-$RBP_PROTEINS/structures/afdb}"
export EMB_BANK="${EMB_BANK:-$AGENT_DB/embedding_bank}"
export FOLDSEEK_DB="${FOLDSEEK_DB:-$AGENT_DB/foldseek_db/refs}"
export SEQ_DB="${SEQ_DB:-$AGENT_DB/seq_db/refs}"
export RBP_REGISTRY="${RBP_REGISTRY:-$AGENT_DB/registry/rbp_registry.json}"
export AF3_DIR="${AF3_DIR:-$_bundle/agent/third_party/alphafold3}"
export AF3_PARAMS="${AF3_PARAMS:-$_bundle/af3_assets/alphafold_param}"
export AF3_CACHE="${AF3_CACHE:-/tmp/af3_cache}"
export AF3_PYTHON="${AF3_PYTHON:-/bin/false}"
echo "  AGENT_DB=$AGENT_DB"
echo "  RHOBIND_RELEASE=$RHOBIND_RELEASE"

if [[ "$WITH_CONDA" == "1" ]]; then
  echo "[2/6] delivery setup_envs.sh (protein_embed=ESM / rna / rhobind / af3) ..."
  if command -v conda >/dev/null 2>&1; then
    bash "$DELIVERY_ROOT/agent/setup_envs.sh"
    _missing=0
    for _env in protein_embed rna rhobind af3; do
      if conda env list 2>/dev/null | awk '{print $1}' | grep -qx "$_env"; then
        echo "  [ok] conda env $_env"
      else
        echo "  [MISSING] conda env $_env" >&2
        _missing=1
      fi
    done
    if [[ "$_missing" == "1" ]]; then
      echo "ERROR: full science stack incomplete. Re-run setup_envs or fix conda." >&2
      exit 1
    fi
    if ! conda run -n rhobind python -c "import transformers" >/dev/null 2>&1; then
      echo "  rhobind missing transformers — installing release requirements ..."
      conda run -n rhobind pip install -r "$RHOBIND_RELEASE/requirements.txt"
    fi
    conda run -n rhobind python -c \
      "import transformers, torch; print('  rhobind OK transformers', transformers.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available())"
    conda run -n protein_embed python -c \
      "import transformers; print('  protein_embed (ESM) OK transformers', transformers.__version__)" \
      || echo "  WARN: protein_embed import check failed" >&2
    if [[ -x "${AF3_PYTHON:-}" && "${AF3_PYTHON}" != "/bin/false" ]]; then
      echo "  af3 OK python=$AF3_PYTHON"
    else
      _af3py="$(conda run -n af3 which python 2>/dev/null || true)"
      if [[ -n "$_af3py" && -x "$_af3py" ]]; then
        export AF3_PYTHON="$_af3py"
        echo "  af3 OK python=$AF3_PYTHON"
      else
        echo "ERROR: af3 env has no usable python" >&2
        exit 1
      fi
    fi
    if [[ "$SKIP_AF3" != "1" ]]; then
      echo "[2b/6] AF3 harden (budget ${AF3_BUDGET_SEC:-600}s; deferred ≠ setup fail) ..."
      AF3_BUDGET_SEC="${AF3_BUDGET_SEC:-600}" _setup_af3 \
        || echo "  WARN: AF3 harden exited non-zero (science stack still usable via AFDB)" >&2
      if [[ -f "$AGENT_ROOT/.af3_status" ]]; then
        echo "  AF3 status: $(tr '\n' ' ' < "$AGENT_ROOT/.af3_status")"
      fi
    else
      echo "[2b/6] skip AF3 harden (--skip-af3)"
    fi
  else
    echo "ERROR: conda not found — cannot build full science stack." >&2
    echo "  Install conda, or re-run with --skip-conda (agent-only, no RhoBind/ESM/AF3)." >&2
    exit 1
  fi
else
  echo "[2/6] skip delivery conda (--skip-conda: agent venv only, no science envs)"
fi

echo "[3/6] Resolving Python >= 3.13 for nanobot ..."
pick_python() {
  local c
  for c in python3.13 python3.14 python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)' 2>/dev/null; then
        echo "$c"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN=""
if PYTHON_BIN="$(pick_python)"; then
  echo "  using $($PYTHON_BIN -V)"
else
  echo "  trying conda env rbp_nanobot (python 3.13) ..."
  if ! command -v conda >/dev/null 2>&1; then
    echo "ERROR: need Python>=3.13 or conda" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  eval "$(conda shell.bash hook)"
  if ! conda env list | awk '{print $1}' | grep -qx 'rbp_nanobot'; then
    conda create -y -n rbp_nanobot python=3.13
  fi
  conda activate rbp_nanobot
  PYTHON_BIN=python
  echo "  using conda rbp_nanobot: $($PYTHON_BIN -V)"
fi

echo "[4/6] venv + pip + nanobot ..."
if [[ ! -d "$AGENT_ROOT/.venv" ]]; then
  "$PYTHON_BIN" -m venv "$AGENT_ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$AGENT_ROOT/.venv/bin/activate"
python -m pip install -U pip setuptools wheel
if [[ ! -f "$AGENT_ROOT/requirements.lock" ]]; then
  echo "ERROR: missing $AGENT_ROOT/requirements.lock (sole App pip pin file)" >&2
  exit 1
fi
echo "  pip install -r requirements.lock (pinned runtime)"
python -m pip install -r "$AGENT_ROOT/requirements.lock"

echo "  install nanobot deps + .pth (flat layout; avoid pip -e)"
mapfile -t _NB_DEPS < <(python - <<PY
import tomllib
from pathlib import Path
p = Path(r"$NANOBOT_SRC") / "pyproject.toml"
for d in tomllib.loads(p.read_text()).get("project", {}).get("dependencies", []):
    print(d)
PY
)
if ((${#_NB_DEPS[@]})); then
  python -m pip install "${_NB_DEPS[@]}"
fi
_SITE="$(python -c 'import site; print(site.getsitepackages()[0])')"
echo "$(cd "$NANOBOT_SRC/.." && pwd)" > "$_SITE/_nanobot_src.pth"
rm -f "$_SITE"/__editable__.nanobot-*.pth \
  "$_SITE"/__editable___nanobot_*_finder.py 2>/dev/null || true
(cd "$BIO_ROOT" && python -c "
import nanobot
from nanobot.agent.tools.base import Tool
p = (nanobot.__file__ or '').replace('\\\\', '/')
print('  nanobot OK', p)
assert '/nanobot-bio/' not in p, p
assert p.endswith('__init__.py') or '/nanobot/' in p, p
")

echo "  sync plugin overlay into nanobot runtime ..."
export NANOBOT_SRC NANOBOT_BIO_ROOT="$AGENT_ROOT" NANOBOT_WORKSPACE="$AGENT_ROOT/workspace"
python -m pip install -e "${AGENT_ROOT}[dev]" -q || python -m pip install -e "$AGENT_ROOT" -q
python -m app.sync_overlay
python -c "from nanobot.agent.tools.rbp.predict import PredictInteractionTool; print('  nanobot.agent.tools.rbp OK', PredictInteractionTool)"

echo "[5/6] .env + workspace skill ..."
_AF3_PY="${AF3_PYTHON:-/bin/false}"
if [[ ! -x "$_AF3_PY" || "$_AF3_PY" == "/bin/false" ]]; then
  for _c in \
    "$HOME/miniconda3/envs/af3/bin/python" \
    "$HOME/miniforge3/envs/af3/bin/python" \
    "$HOME/mambaforge/envs/af3/bin/python" \
    "$HOME/anaconda3/envs/af3/bin/python"
  do
    [[ -x "$_c" ]] && _AF3_PY="$_c" && break
  done
  if [[ ! -x "$_AF3_PY" || "$_AF3_PY" == "/bin/false" ]] && command -v conda >/dev/null 2>&1; then
    if conda env list 2>/dev/null | awk '{print $1}' | grep -qx af3; then
      _AF3_PY="$(conda run -n af3 which python 2>/dev/null || true)"
    fi
  fi
fi
export AF3_PYTHON="${_AF3_PY:-/bin/false}"

cat > "$AGENT_ROOT/.env" <<EOF
# Generated by setup_all.sh on Linux server
BIO_ROOT=$BIO_ROOT
DELIVERY_ROOT=$DELIVERY_ROOT
NANOBOT_SRC=$NANOBOT_SRC
NANOBOT_BIO_ROOT=$AGENT_ROOT
NANOBOT_WORKSPACE=$AGENT_ROOT/workspace
AGENT_DB=${AGENT_DB:-$DELIVERY_ROOT/agent_db}
RBP_REGISTRY=${RBP_REGISTRY:-$DELIVERY_ROOT/agent_db/registry/rbp_registry.json}
RHOBIND_RELEASE=${RHOBIND_RELEASE:-$DELIVERY_ROOT/release/rhobind_release_v1}
RBP_PROTEINS=${RBP_PROTEINS:-$DELIVERY_ROOT/reference}
AFDB_DIR=${AFDB_DIR:-$DELIVERY_ROOT/reference/structures/afdb}
TRANSFER_DIR=${TRANSFER_DIR:-$DELIVERY_ROOT/agent_db/transfer}
EMB_BANK=${EMB_BANK:-$DELIVERY_ROOT/agent_db/embedding_bank}
FOLDSEEK_DB=${FOLDSEEK_DB:-$DELIVERY_ROOT/agent_db/foldseek_db/refs}
SEQ_DB=${SEQ_DB:-$DELIVERY_ROOT/agent_db/seq_db/refs}
PEAKS_DB=${PEAKS_DB:-$DELIVERY_ROOT/agent_db/peaks_db/peaks}
USALIGN=${USALIGN:-$DELIVERY_ROOT/agent_db/bin/USalign}
AF3_DIR=${AF3_DIR:-$DELIVERY_ROOT/agent/third_party/alphafold3}
AF3_PARAMS=${AF3_PARAMS:-$DELIVERY_ROOT/af3_assets/alphafold_param}
AF3_PYTHON=${AF3_PYTHON:-/bin/false}
RHOBIND_DEVICE=${RHOBIND_DEVICE:-auto}
RBP_BACKEND=delivery
EOF

chmod +x "$AGENT_ROOT/scripts/setup_all.sh" 2>/dev/null || true

mkdir -p "$AGENT_ROOT/workspace/skills/rbp-agent" \
  "$AGENT_ROOT/workspace/memory"
PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "
from app.core.paths import ensure_artifact_dirs, migrate_flat_artifacts
ensure_artifact_dirs()
migrate_flat_artifacts()
print('[setup] artifacts dirs OK')
" || mkdir -p \
  "$AGENT_ROOT/artifacts/traces" \
  "$AGENT_ROOT/artifacts/sessions" \
  "$AGENT_ROOT/artifacts/reports" \
  "$AGENT_ROOT/artifacts/cache" \
  "$AGENT_ROOT/artifacts/logs" \
  "$AGENT_ROOT/artifacts/diag"
# Always sync SoT plugin overlay → runtime + workspace
echo "[sync] plugin overlay → NANOBOT_SRC + workspace ..."
export PYTHONPATH="$BIO_ROOT:$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
python -m app.sync_overlay || {
  echo "WARN: sync_overlay failed (NANOBOT_SRC may be incomplete); doctor will retry" >&2
}
# Ensure workspace skill marker stays present after sync
cat > "$AGENT_ROOT/workspace/skills/rbp-agent/DO_NOT_EDIT.md" <<'EOF'
# Generated by sync — do not hand-edit

Edit the SoT (source-of-truth) instead:

  nanobot/skills/rbp-agent/SKILL.md

Then run: `python -m app.sync_overlay` or `rbp-agent doctor`.
EOF

if [[ "$SKIP_SMOKE" != "1" ]]; then
  echo "[6/6] Smoke + verify ..."
  python -m app doctor
  python -m app nanobot-smoke || true
else
  echo "[6/6] skip smoke"
fi

_STAMP="$AGENT_ROOT/.setup_complete"
{
  echo "setup_all_ts=$(date -Iseconds 2>/dev/null || date)"
  echo "with_conda=$WITH_CONDA"
  echo "nanobot_src=$NANOBOT_SRC"
  echo "af3_python=$AF3_PYTHON"
  echo "python=$(command -v python 2>/dev/null || true)"
} > "$_STAMP"
echo "  wrote $_STAMP"

echo
echo " setup_all.sh done — full advanced env configured once."
echo " Every later SSH session:"
echo "   source $AGENT_ROOT/.venv/bin/activate"
echo "   rbp-agent doctor && rbp-agent chat"
echo " Re-run full setup after pulls / new GPU host:"
echo "   bash $AGENT_ROOT/scripts/setup_all.sh"
echo " Agent-only (no conda science): bash $AGENT_ROOT/scripts/setup_all.sh --skip-conda"
