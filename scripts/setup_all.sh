#!/usr/bin/env bash
# =============================================================================
# nanobot-bio 环境配置 — 仅面向 Linux / SSH 服务器
# =============================================================================
# 提案框架: nanobot（必须可 import）
# 工具后端: rhobind_agent_delivery（AGENT_BUILD_SPEC）
#
# 推荐总入口（仓库根）::
#   bash ../scripts/setup_linux_server.sh [--with-conda]
#
# 或本脚本::
#   cd /path/to/bio_agent/nanobot-bio
#   export NANOBOT_SRC=/path/to/nanobot
#   bash scripts/setup_all.sh [--with-conda] [--skip-smoke]
#
# nanobot 要求 Python >= 3.13。不够则尝试 conda env rbp_nanobot。
# =============================================================================
set -euo pipefail

WITH_CONDA=0
SKIP_SMOKE=0
for arg in "$@"; do
  case "$arg" in
    --with-conda) WITH_CONDA=1 ;;
    --skip-smoke) SKIP_SMOKE=1 ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIO_ROOT="$(cd "${BIO_ROOT:-$AGENT_ROOT/..}" && pwd)"
DELIVERY_ROOT="${DELIVERY_ROOT:-$BIO_ROOT/rhobind_agent_delivery}"
NANOBOT_SRC="${NANOBOT_SRC:-$AGENT_ROOT/nanobot}"

echo "=============================================="
echo " nanobot-bio setup (Linux / proposal nanobot)"
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
export DELIVERY_ROOT AGENT_ROOT BIO_ROOT
export NANOBOT_BIO_ROOT="$AGENT_ROOT"
export NANOBOT_WORKSPACE="$AGENT_ROOT/workspace"
export NANOBOT_SRC
echo "  AGENT_DB=$AGENT_DB"
echo "  RHOBIND_RELEASE=$RHOBIND_RELEASE"

if [[ "$WITH_CONDA" == "1" ]]; then
  echo "[2/6] delivery setup_envs.sh ..."
  if command -v conda >/dev/null 2>&1; then
    bash "$DELIVERY_ROOT/agent/setup_envs.sh"
  else
    echo "WARNING: conda not found" >&2
  fi
else
  echo "[2/6] skip delivery conda (use --with-conda on GPU server)"
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
python -m pip install -r "$AGENT_ROOT/requirements.txt"

if [[ ! -f "$NANOBOT_SRC/pyproject.toml" ]] && [[ ! -f "$NANOBOT_SRC/nanobot.py" ]]; then
  echo "ERROR: nanobot not at $NANOBOT_SRC" >&2
  echo "  Run: bash $BIO_ROOT/scripts/setup_linux_server.sh" >&2
  exit 1
fi
echo "  install nanobot deps + make importable (flat layout)"
# HKUDS nanobot keeps package modules at repo root; setuptools editable
# install fails with "Multiple top-level packages". Use deps + .pth instead.
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
# Parent of package dir must be on sys.path so `import nanobot` resolves.
echo "$(cd "$NANOBOT_SRC/.." && pwd)" > "$_SITE/_nanobot_src.pth"
python -c "import nanobot; from nanobot.agent.tools.base import Tool; print('  nanobot OK', nanobot.__file__)"

# 提案 §6.2：把 nanobot/agent/tools/rbp 安装进真实 nanobot 包树
echo "  install RBP tools into nanobot package tree ..."
export NANOBOT_SRC NANOBOT_BIO_ROOT="$AGENT_ROOT" NANOBOT_WORKSPACE="$AGENT_ROOT/workspace"
python "$AGENT_ROOT/scripts/install_rbp_into_nanobot.py"
python -c "from nanobot.agent.tools.rbp.predict import PredictInteractionTool; print('  nanobot.agent.tools.rbp OK', PredictInteractionTool)"

echo "[5/6] .env + activate_env.sh + workspace skill ..."
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
RHOBIND_DEVICE=${RHOBIND_DEVICE:-cpu}
RBP_BACKEND=delivery
EOF

cat > "$AGENT_ROOT/scripts/activate_env.sh" <<EOF
#!/usr/bin/env bash
# Every SSH session:  source $AGENT_ROOT/scripts/activate_env.sh
_AGENT_ROOT="$AGENT_ROOT"
_DELIVERY_ROOT="$DELIVERY_ROOT"
_NANOBOT_SRC="$NANOBOT_SRC"
# shellcheck disable=SC1091
source "\$_DELIVERY_ROOT/agent/setup.sh"
# shellcheck disable=SC1091
source "\$_AGENT_ROOT/.venv/bin/activate"
export BIO_ROOT="$BIO_ROOT"
export DELIVERY_ROOT="\$_DELIVERY_ROOT"
export NANOBOT_SRC="\$_NANOBOT_SRC"
export NANOBOT_BIO_ROOT="\$_AGENT_ROOT"
export NANOBOT_WORKSPACE="\$_AGENT_ROOT/workspace"
# BIO_ROOT before AGENT_ROOT so real nanobot/ wins over nanobot-bio/nanobot stub
export PYTHONPATH="\$(cd "\$_NANOBOT_SRC/.." && pwd):\$_AGENT_ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
if [[ -f "\$_AGENT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "\$_AGENT_ROOT/.env"
  set +a
fi
echo "[activate_env] DELIVERY_ROOT=\$DELIVERY_ROOT NANOBOT_SRC=\$NANOBOT_SRC"
echo "[activate_env] \$(python -V) \$(command -v python)"
# Verify from BIO_ROOT so cwd cannot shadow via nanobot-bio/nanobot stub
( cd "\$BIO_ROOT" && python -c "import nanobot; print('[activate_env] nanobot OK', nanobot.__file__)" ) \
  2>/dev/null || echo "[activate_env] WARN: nanobot import failed"
EOF
chmod +x "$AGENT_ROOT/scripts/activate_env.sh" "$AGENT_ROOT/scripts/setup_all.sh" 2>/dev/null || true

mkdir -p "$AGENT_ROOT/workspace/skills/rbp-agent" \
  "$AGENT_ROOT/workspace/sessions" \
  "$AGENT_ROOT/workspace/memory" \
  "$AGENT_ROOT/rbp_eval/traces"
[[ -f "$AGENT_ROOT/nanobot/skills/rbp-agent/SKILL.md" ]] && \
  cp -f "$AGENT_ROOT/nanobot/skills/rbp-agent/SKILL.md" "$AGENT_ROOT/workspace/skills/rbp-agent/SKILL.md"

if [[ "$SKIP_SMOKE" != "1" ]]; then
  echo "[6/6] Smoke ..."
  export PYTHONPATH="$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
  python "$AGENT_ROOT/cli.py" doctor
  python "$AGENT_ROOT/cli.py" nanobot-smoke || true
else
  echo "[6/6] skip smoke"
fi

echo
echo " setup_all.sh done. Next SSH session:"
echo "   source $AGENT_ROOT/scripts/activate_env.sh"
echo "   pip install -e $AGENT_ROOT"
echo "   rbp-agent doctor && rbp-agent chat"
