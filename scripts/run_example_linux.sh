#!/usr/bin/env bash
# End-to-end example aligned with delivery agent/examples/run_example.sh
# but through the agent pipeline (Linux).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$AGENT_ROOT/scripts/activate_env.sh"

DEVICE="${1:-cpu}"
FORCE_OFFLINE_DOMAIN_ONLY="${2:-0}"

EX="$DELIVERY_ROOT/agent/examples"
OUT="$AGENT_ROOT/out"
mkdir -p "$OUT"

echo "### Agent pipeline: PTBP1 force_transfer ###"
if [[ "$FORCE_OFFLINE_DOMAIN_ONLY" == "1" ]]; then
  python "$AGENT_ROOT/cli.py" run \
    --query PTBP1 \
    --uniprot P26599 \
    --sequence-fasta "$EX/new_rbp_PTBP1.fasta" \
    --rna-file "$EX/sample_rna_pos.txt" \
    --force-transfer \
    --offline \
    --no-embedding \
    --no-sequence \
    --device "$DEVICE" \
    --out "$OUT/ptbp1_transfer_domain.json"
else
  python "$AGENT_ROOT/cli.py" run \
    --query PTBP1 \
    --uniprot P26599 \
    --sequence-fasta "$EX/new_rbp_PTBP1.fasta" \
    --rna-file "$EX/sample_rna_pos.txt" \
    --force-transfer \
    --device "$DEVICE" \
    --out "$OUT/ptbp1_transfer_full.json"
fi

echo "### Optional: delivery native golden smoke ###"
echo "bash \$DELIVERY_ROOT/agent/examples/run_example.sh $DEVICE"
