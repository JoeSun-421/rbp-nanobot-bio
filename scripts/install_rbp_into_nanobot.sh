#!/usr/bin/env bash
# Sync workspace skill from nested nanobot (proposal §6.2).
set -euo pipefail
NANOBOT_BIO_ROOT="${NANOBOT_BIO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
NANOBOT_SRC="${NANOBOT_SRC:-$NANOBOT_BIO_ROOT/nanobot}"
WORKSPACE="${NANOBOT_WORKSPACE:-$NANOBOT_BIO_ROOT/workspace}"
SRC_SKILL="$NANOBOT_SRC/skills/rbp-agent/SKILL.md"
[[ -f "$SRC_SKILL" ]] || { echo "ERROR: missing $SRC_SKILL" >&2; exit 1; }
mkdir -p "$WORKSPACE/skills/rbp-agent"
cp -f "$SRC_SKILL" "$WORKSPACE/skills/rbp-agent/SKILL.md"
echo "[install_rbp] skill -> $WORKSPACE/skills/rbp-agent/SKILL.md"
echo "[install_rbp] tools SoT: $NANOBOT_SRC/agent/tools/rbp"
echo "[install_rbp] DONE"
