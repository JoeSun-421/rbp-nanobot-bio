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
#   export NANOBOT_SRC=/path/to/nanobot   # optional; default $BIO_ROOT/nanobot
#   export NANOBOT_GIT=https://github.com/HKUDS/nanobot.git
#   bash scripts/setup_all.sh                 # 默认：完整高级环境（含 delivery conda）
#   bash scripts/setup_all.sh --skip-conda    # 仅 agent venv（无 GPU 科学栈）
#   bash scripts/setup_all.sh --skip-smoke
#
# 默认一次性配置全部高级依赖（protein_embed / rna / rhobind / af3 + agent venv）。
# 日常 SSH 用 light activate；不要把 setup 拆进每次 source。
# 若旁路 nanobot 不存在，自动 git clone HKUDS/nanobot（可用 NANOBOT_NO_CLONE=1 禁用）。
# nanobot 要求 Python >= 3.13。不够则尝试 conda env rbp_nanobot。
# =============================================================================
set -euo pipefail

# Product default: full science stack once. Opt out with --skip-conda.
WITH_CONDA=1
SKIP_SMOKE=0
for arg in "$@"; do
  case "$arg" in
    --with-conda) WITH_CONDA=1 ;;  # kept for back-compat (now default)
    --skip-conda) WITH_CONDA=0 ;;
    --skip-smoke) SKIP_SMOKE=1 ;;
    -h|--help) sed -n '1,40p' "$0"; exit 0 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIO_ROOT="$(cd "${BIO_ROOT:-$AGENT_ROOT/..}" && pwd)"
DELIVERY_ROOT="${DELIVERY_ROOT:-$BIO_ROOT/rhobind_agent_delivery}"
NANOBOT_SRC="${NANOBOT_SRC:-$BIO_ROOT/nanobot}"
export BIO_ROOT NANOBOT_SRC
# shellcheck disable=SC1091
source "$SCRIPT_DIR/ensure_nanobot_runtime.sh"
NANOBOT_SRC="${NANOBOT_SRC}"

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
  echo "[2/6] delivery setup_envs.sh (protein_embed=ESM / rna / rhobind / af3) ..."
  if command -v conda >/dev/null 2>&1; then
    bash "$DELIVERY_ROOT/agent/setup_envs.sh"
    # Require all science envs — fail setup if any missing
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
    # Harden existing rhobind env: ensure transformers (common failure mode)
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
python -m pip install -r "$AGENT_ROOT/requirements.txt"

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

# 提案 §6.2：把 nanobot/agent/tools/rbp 安装进真实 nanobot 包树
echo "  install RBP tools into nanobot package tree ..."
export NANOBOT_SRC NANOBOT_BIO_ROOT="$AGENT_ROOT" NANOBOT_WORKSPACE="$AGENT_ROOT/workspace"
python "$AGENT_ROOT/scripts/install_rbp_into_nanobot.py"
python -c "from nanobot.agent.tools.rbp.predict import PredictInteractionTool; print('  nanobot.agent.tools.rbp OK', PredictInteractionTool)"

echo "[5/6] .env + workspace skill (activate_env.sh is maintained in-repo; not overwritten) ..."
# Resolve AF3 python once so light activate never needs conda probe
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

python -m pip install -e "$AGENT_ROOT" -q

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

chmod +x "$AGENT_ROOT/scripts/activate_env.sh" "$AGENT_ROOT/scripts/setup_all.sh" 2>/dev/null || true

mkdir -p "$AGENT_ROOT/workspace/skills/rbp-agent" \
  "$AGENT_ROOT/workspace/sessions" \
  "$AGENT_ROOT/workspace/memory" \
  "$AGENT_ROOT/rbp_eval/traces"
[[ -f "$AGENT_ROOT/nanobot/skills/rbp-agent/SKILL.md" ]] && \
  cp -f "$AGENT_ROOT/nanobot/skills/rbp-agent/SKILL.md" "$AGENT_ROOT/workspace/skills/rbp-agent/SKILL.md"

if [[ "$SKIP_SMOKE" != "1" ]]; then
  echo "[6/6] Smoke + full verify ..."
  export PYTHONPATH="$BIO_ROOT:$AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
  python "$AGENT_ROOT/cli.py" doctor
  python "$AGENT_ROOT/cli.py" nanobot-smoke || true
  # One-shot heavy path in a subshell (pip -e + RBP sync + import verify)
  # Does not replace setup — only re-syncs overlay after the full install above.
  (
    # shellcheck disable=SC1091
    ACTIVATE_HEAVY=1 ACTIVATE_VERIFY=1 source "$AGENT_ROOT/scripts/activate_env.sh"
  ) || echo "[setup] WARN: heavy activate verify had warnings"
else
  echo "[6/6] skip smoke"
fi

# Stamp: light activate expects this after a full setup
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
echo " Every later SSH session (light, fast):"
echo "   source $AGENT_ROOT/scripts/activate_env.sh"
echo "   rbp-agent doctor && rbp-agent chat"
echo " Re-run full setup after pulls / new GPU host:"
echo "   bash $AGENT_ROOT/scripts/setup_all.sh"
echo " Agent-only (no conda science): bash $AGENT_ROOT/scripts/setup_all.sh --skip-conda"
