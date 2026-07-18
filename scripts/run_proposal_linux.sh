#!/usr/bin/env bash
# One-shot Nanobot.run smoke on Linux (agent path only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$AGENT_ROOT/scripts/activate_env.sh"

MSG="${1:-Does this RNA interact with RBP PTBP1? RNA: AUGGCUAGCUAGC; target_uniprot: P26599. End with verdict JSON.}"
if command -v rbp-agent >/dev/null 2>&1; then
  exec rbp-agent agent --strict --message "$MSG"
fi
exec python "$AGENT_ROOT/cli.py" agent --strict --message "$MSG"
