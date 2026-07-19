#!/usr/bin/env bash
# Usage: source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh
#
# Default = light (~tens of ms): venv + env exports + OMP + PYTHONPATH/.pth
# Full advanced stack (conda science envs, pip, RBP sync) is configured ONCE by:
#   bash scripts/setup_all.sh              # default includes delivery conda
#   bash scripts/setup_all.sh --skip-conda # agent venv only
#
# Heavy re-sync after code pulls (not a substitute for first-time setup):
#   ACTIVATE_HEAVY=1 source …/activate_env.sh
# Optional import check only:
#   ACTIVATE_VERIFY=1 source …/activate_env.sh
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_AGENT_ROOT="$(cd "$_SCRIPT_DIR/.." && pwd)"
_BIO_ROOT="$(cd "${BIO_ROOT:-$_AGENT_ROOT/..}" && pwd)"
_DELIVERY_ROOT="${DELIVERY_ROOT:-$_BIO_ROOT/rhobind_agent_delivery}"
_NANOBOT_SRC_DEFAULT="$_BIO_ROOT/nanobot"
_ACTIVATE_HEAVY="${ACTIVATE_HEAVY:-0}"
_ACTIVATE_VERIFY="${ACTIVATE_VERIFY:-0}"

# First-time: require setup_all (writes .setup_complete). Light activate alone is not enough.
if [[ ! -f "$_AGENT_ROOT/.setup_complete" ]]; then
  echo "[activate_env] WARN: full setup not finished (missing $_AGENT_ROOT/.setup_complete)" >&2
  echo "[activate_env]        Run once:  bash $_AGENT_ROOT/scripts/setup_all.sh" >&2
  echo "[activate_env]        (default installs protein_embed/rna/rhobind/af3 + agent venv)" >&2
fi

# AF3: prefer .env / known env layouts — never probe conda on the light path
if [[ -z "${AF3_PYTHON:-}" || "${AF3_PYTHON}" == "/bin/false" ]]; then
  _af3_cands=()
  if [[ -n "${CONDA_ENVS_PATH:-}" ]]; then
    IFS=':' read -r -a _dirs <<< "$CONDA_ENVS_PATH"
    for _d in "${_dirs[@]}"; do
      [[ -n "$_d" ]] && _af3_cands+=("${_d%/}/af3/bin/python")
    done
  fi
  _af3_cands+=(
    "${HOME}/miniconda3/envs/af3/bin/python"
    "${HOME}/miniforge3/envs/af3/bin/python"
    "${HOME}/mambaforge/envs/af3/bin/python"
    "${HOME}/anaconda3/envs/af3/bin/python"
  )
  for _af3 in "${_af3_cands[@]}"; do
    if [[ -x "$_af3" ]]; then
      export AF3_PYTHON="$_af3"
      break
    fi
  done
fi
# Heavy only: conda probe when still unset (works for non-default env prefixes)
if [[ "$_ACTIVATE_HEAVY" == "1" && ( -z "${AF3_PYTHON:-}" || "${AF3_PYTHON}" == "/bin/false" ) ]]; then
  if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | awk '{print $1}' | grep -qx af3; then
    AF3_PYTHON="$(conda run -n af3 which python 2>/dev/null || true)"
  fi
fi
export AF3_PYTHON="${AF3_PYTHON:-/bin/false}"

if [[ -f "$_DELIVERY_ROOT/agent/setup.sh" ]]; then
  # shellcheck disable=SC1091
  source "$_DELIVERY_ROOT/agent/setup.sh"
fi
# shellcheck disable=SC1091
source "$_AGENT_ROOT/.venv/bin/activate"

# Sanitize OpenMP thread vars: 0/empty is rejected by libgomp
_omp_sane() {
  case "${1:-}" in
    ''|0|*[!0-9]*) return 1 ;;
    *) return 0 ;;
  esac
}
if ! _omp_sane "$OMP_NUM_THREADS"; then
  export OMP_NUM_THREADS=4
fi
_omp_sane "${MKL_NUM_THREADS:-}" || export MKL_NUM_THREADS="$OMP_NUM_THREADS"
_omp_sane "${OPENBLAS_NUM_THREADS:-}" || export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"

export BIO_ROOT="$_BIO_ROOT"
export DELIVERY_ROOT="$_DELIVERY_ROOT"
export NANOBOT_BIO_ROOT="$_AGENT_ROOT"
export NANOBOT_WORKSPACE="${NANOBOT_WORKSPACE:-$_AGENT_ROOT/workspace}"

export HF_HOME="${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
# Optional mirror (override/unset for official Hub)
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
mkdir -p "$HF_HOME/hub" "$TRANSFORMERS_CACHE" 2>/dev/null || true

if [[ -f "$_AGENT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$_AGENT_ROOT/.env"
  set +a
fi

_NANOBOT_SRC="${NANOBOT_SRC:-$_NANOBOT_SRC_DEFAULT}"
case "$_NANOBOT_SRC" in
  *"nanobot-bio/nanobot"|*"nanobot-bio/nanobot/")
    if [[ ! -f "$_NANOBOT_SRC/nanobot.py" ]]; then
      _NANOBOT_SRC="$_NANOBOT_SRC_DEFAULT"
    fi
    ;;
esac
export NANOBOT_SRC="$_NANOBOT_SRC"
export BIO_ROOT="$_BIO_ROOT"

# Ensure runtime: fast no-op when sibling exists; clone only if missing
# shellcheck disable=SC1091
source "$_AGENT_ROOT/scripts/ensure_nanobot_runtime.sh"
_NANOBOT_SRC="$NANOBOT_SRC"

export PYTHONPATH="${_BIO_ROOT}:${_AGENT_ROOT}${PYTHONPATH:+:$PYTHONPATH}"

# Flat-layout nanobot: BIO_ROOT via .pth (idempotent, cheap)
if command -v python >/dev/null 2>&1; then
  _SITE="$(python -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null || true)"
  if [[ -n "$_SITE" ]]; then
    echo "$_BIO_ROOT" > "$_SITE/_nanobot_src.pth"
  fi
fi

if [[ "$_ACTIVATE_HEAVY" == "1" ]]; then
  if [[ -n "${_SITE:-}" ]]; then
    rm -f "$_SITE"/__editable__.nanobot-*.pth \
      "$_SITE"/__editable___nanobot_*_finder.py 2>/dev/null || true
  fi
  pip install -e "$_AGENT_ROOT" -q 2>/dev/null \
    || echo "[activate_env] WARN: pip install -e nanobot-bio failed"
  python "$_AGENT_ROOT/scripts/install_rbp_into_nanobot.py" \
    || echo "[activate_env] WARN: install_rbp_into_nanobot failed"
  _ACTIVATE_VERIFY=1
fi

echo "[activate_env] BIO_ROOT=$BIO_ROOT DELIVERY_ROOT=$DELIVERY_ROOT"
echo "[activate_env] NANOBOT_SRC=$NANOBOT_SRC"
echo "[activate_env] $(python -V 2>/dev/null) $(command -v python 2>/dev/null)"

if [[ "$_ACTIVATE_VERIFY" == "1" ]]; then
  (
    cd "$_BIO_ROOT"
    python - <<'PY'
import nanobot
from nanobot.agent.tools.base import Tool  # noqa: F401
p = (nanobot.__file__ or "").replace("\\", "/")
print("[activate_env] nanobot OK", p)
if "/nanobot-bio/" in p:
    raise SystemExit("[activate_env] ERROR: nanobot shadowed by nanobot-bio overlay")
if p.endswith("/nanobot.py") and "/nanobot/nanobot.py" not in p:
    raise SystemExit("[activate_env] ERROR: imported nanobot.py module, not package")
PY
  ) || echo "[activate_env] WARN: nanobot import failed"
fi

command -v rbp-agent >/dev/null 2>&1 && echo "[activate_env] rbp-agent=$(command -v rbp-agent)" \
  || echo "[activate_env] tip: ACTIVATE_HEAVY=1 source …  # or: pip install -e \$NANOBOT_BIO_ROOT"
