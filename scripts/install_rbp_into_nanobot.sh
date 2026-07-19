#!/usr/bin/env bash
# Sync proposal §6.2 SoT → installed nanobot runtime + workspace.
set -euo pipefail
NANOBOT_BIO_ROOT="${NANOBOT_BIO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
exec python "$NANOBOT_BIO_ROOT/scripts/install_rbp_into_nanobot.py"
