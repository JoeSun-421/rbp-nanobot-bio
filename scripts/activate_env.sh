#!/usr/bin/env bash
# Usage: source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_AGENT_ROOT="$(cd "$_SCRIPT_DIR/.." && pwd)"
_BIO_ROOT="$(cd "${BIO_ROOT:-$_AGENT_ROOT/..}" && pwd)"
_DELIVERY_ROOT="${DELIVERY_ROOT:-$_BIO_ROOT/rhobind_agent_delivery}"
_NANOBOT_SRC="${NANOBOT_SRC:-$_AGENT_ROOT/nanobot}"

if [[ -z "${AF3_PYTHON:-}" ]]; then
  if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | awk '{print $1}' | grep -qx af3; then
    AF3_PYTHON="$(conda run -n af3 which python 2>/dev/null || true)"
  fi
  export AF3_PYTHON="${AF3_PYTHON:-/bin/false}"
fi

if [[ -f "$_DELIVERY_ROOT/agent/setup.sh" ]]; then
  # shellcheck disable=SC1091
  source "$_DELIVERY_ROOT/agent/setup.sh"
fi
# shellcheck disable=SC1091
source "$_AGENT_ROOT/.venv/bin/activate"

export BIO_ROOT="$_BIO_ROOT"
export DELIVERY_ROOT="$_DELIVERY_ROOT"
export NANOBOT_SRC="$_NANOBOT_SRC"
export NANOBOT_BIO_ROOT="$_AGENT_ROOT"
export NANOBOT_WORKSPACE="${NANOBOT_WORKSPACE:-$_AGENT_ROOT/workspace}"
export PYTHONPATH="$_AGENT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Hugging Face / ESM weights on data disk; prefer hf-mirror when HF is blocked
export HF_HOME="${HF_HOME:-/root/autodl-tmp/hf-cache}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
mkdir -p "$HF_HOME/hub" "$TRANSFORMERS_CACHE"

if [[ -f "$_AGENT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$_AGENT_ROOT/.env"
  set +a
fi

echo "[activate_env] BIO_ROOT=$BIO_ROOT DELIVERY_ROOT=$DELIVERY_ROOT"
echo "[activate_env] NANOBOT_SRC=$NANOBOT_SRC"
echo "[activate_env] $(python -V) $(command -v python)"
( cd "$_AGENT_ROOT" && python -c "import nanobot; print('[activate_env] nanobot OK', nanobot.__file__)" ) \
  2>/dev/null || echo "[activate_env] WARN: nanobot import failed"
command -v rbp-agent >/dev/null 2>&1 && echo "[activate_env] rbp-agent=$(command -v rbp-agent)" \
  || echo "[activate_env] tip: pip install -e \$NANOBOT_BIO_ROOT  # for rbp-agent command"
