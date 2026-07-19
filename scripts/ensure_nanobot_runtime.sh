#!/usr/bin/env bash
# Ensure sibling nanobot runtime exists; clone HKUDS/nanobot if missing.
#
# Usage:
#   source scripts/ensure_nanobot_runtime.sh   # exports NANOBOT_SRC
#
# Env:
#   BIO_ROOT / NANOBOT_SRC / NANOBOT_GIT
#   NANOBOT_NO_CLONE=1     — fail instead of cloning
#   NANOBOT_CLONE_TIMEOUT  — seconds per clone attempt (default 180)
set -euo pipefail

_ENSURE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_ENSURE_AGENT_ROOT="$(cd "$_ENSURE_SCRIPT_DIR/.." && pwd)"
_ENSURE_BIO_ROOT="$(cd "${BIO_ROOT:-$_ENSURE_AGENT_ROOT/..}" && pwd)"
NANOBOT_GIT_DEFAULT="https://github.com/HKUDS/nanobot.git"
NANOBOT_GIT="${NANOBOT_GIT:-$NANOBOT_GIT_DEFAULT}"
NANOBOT_SRC="${NANOBOT_SRC:-$_ENSURE_BIO_ROOT/nanobot}"
NANOBOT_CLONE_TIMEOUT="${NANOBOT_CLONE_TIMEOUT:-180}"

# Never treat the §6.2 overlay as the runtime
case "$NANOBOT_SRC" in
  *"nanobot-bio/nanobot"|*"nanobot-bio/nanobot/")
    if [[ ! -f "$NANOBOT_SRC/nanobot.py" && ! -f "$NANOBOT_SRC/pyproject.toml" ]]; then
      NANOBOT_SRC="$_ENSURE_BIO_ROOT/nanobot"
    fi
    ;;
esac

_nanobot_ok() {
  local d="$1"
  [[ -f "$d/__init__.py" || -f "$d/nanobot.py" || -f "$d/pyproject.toml" ]]
}

if _nanobot_ok "$NANOBOT_SRC"; then
  echo "[ensure_nanobot] OK: $NANOBOT_SRC"
  export NANOBOT_SRC BIO_ROOT="$_ENSURE_BIO_ROOT"
  return 0 2>/dev/null || exit 0
fi

if [[ "${NANOBOT_NO_CLONE:-0}" == "1" ]]; then
  echo "ERROR: nanobot runtime missing at $NANOBOT_SRC (NANOBOT_NO_CLONE=1)" >&2
  return 1 2>/dev/null || exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git required to clone nanobot into $NANOBOT_SRC" >&2
  return 1 2>/dev/null || exit 1
fi

if [[ -e "$NANOBOT_SRC" ]]; then
  if [[ -d "$NANOBOT_SRC" ]] && [[ -z "$(ls -A "$NANOBOT_SRC" 2>/dev/null || true)" ]]; then
    rmdir "$NANOBOT_SRC" 2>/dev/null || true
  elif [[ -d "$NANOBOT_SRC" ]] && ! _nanobot_ok "$NANOBOT_SRC"; then
    if [[ -d "$NANOBOT_SRC/skills/rbp-agent" || -d "$NANOBOT_SRC/agent/tools/rbp" ]]; then
      echo "ERROR: $NANOBOT_SRC looks like §6.2 overlay, not runtime." >&2
      echo "  Set NANOBOT_SRC=\$BIO_ROOT/nanobot (sibling) and re-run." >&2
      return 1 2>/dev/null || exit 1
    fi
    echo "WARN: incomplete nanobot at $NANOBOT_SRC — moving aside" >&2
    mv "$NANOBOT_SRC" "${NANOBOT_SRC}.bak.$(date +%s)"
  fi
fi

# Prefer explicit NANOBOT_GIT; then direct GitHub; then common mirrors (CN).
_urls=()
_urls+=("$NANOBOT_GIT")
if [[ "$NANOBOT_GIT" == "$NANOBOT_GIT_DEFAULT" ]]; then
  _urls+=(
    "https://ghproxy.net/https://github.com/HKUDS/nanobot.git"
    "https://mirror.ghproxy.com/https://github.com/HKUDS/nanobot.git"
    "https://gitclone.com/github.com/HKUDS/nanobot.git"
  )
fi

mkdir -p "$(dirname "$NANOBOT_SRC")"
_cloned=0
export GIT_TERMINAL_PROMPT=0
for _url in "${_urls[@]}"; do
  echo "[ensure_nanobot] cloning (${NANOBOT_CLONE_TIMEOUT}s) $_url → $NANOBOT_SRC"
  rm -rf "$NANOBOT_SRC"
  _ok=0
  if command -v timeout >/dev/null 2>&1; then
    # -k: kill git children if still alive after soft timeout
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
  echo "  Or set NANOBOT_GIT=<reachable-mirror-url>" >&2
  return 1 2>/dev/null || exit 1
fi

echo "[ensure_nanobot] cloned OK: $NANOBOT_SRC"
export NANOBOT_SRC BIO_ROOT="$_ENSURE_BIO_ROOT"
return 0 2>/dev/null || exit 0
