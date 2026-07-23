# -*- coding: utf-8 -*-
"""RNA-FM eval gate: open fusion only with real checkpoint + smoke evidence."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.backends.rna_fm.policy import (
    DEFAULT_REAL_WEIGHT,
    checkpoint_path,
    checkpoint_ready,
    write_gate,
)


def run_rna_fm_gate(*, fusion_weight: float = DEFAULT_REAL_WEIGHT) -> dict[str, Any]:
    """Smoke-test real checkpoint (if any) and write allow/hold gate JSON."""
    from app.backends.rna_fm.client import RnaFmClient, ensure_default_bank

    ensure_default_bank()
    ckpt = checkpoint_path()
    now = datetime.now(timezone.utc).isoformat()
    if not ckpt:
        gate = {
            "schema": "rna_fm_eval_gate.v1",
            "generated_at": now,
            "allow_fusion": False,
            "decision": "HOLD",
            "reason": "RNA_FM_CHECKPOINT unset or path missing — fusion rna_*=0",
            "checkpoint": None,
            "fusion_weight": 0.0,
        }
        write_gate(gate)
        return gate

    # Real path: require embed smoke on a short fixture RNA
    client = RnaFmClient(mode="real")
    try:
        hits = client.similarity(
            "AUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUA",
            top_k=3,
        )
        # Also force one real embed call
        vec = client._embed_real("ACGUACGUACGUACGUACGUACGUACGUACGU")
        ok = isinstance(vec, list) and len(vec) >= 8 and isinstance(hits, list)
        if not ok:
            raise RuntimeError("embed/similarity smoke returned empty")
        gate = {
            "schema": "rna_fm_eval_gate.v1",
            "generated_at": now,
            "allow_fusion": True,
            "decision": "PROMOTE",
            "reason": (
                f"checkpoint ok path={ckpt}; embed_dim={len(vec)}; "
                f"n_hits={len(hits)}; fusion_weight={fusion_weight}"
            ),
            "checkpoint": str(ckpt),
            "fusion_weight": float(fusion_weight),
            "smoke": {"embed_dim": len(vec), "n_hits": len(hits)},
        }
    except Exception as e:
        gate = {
            "schema": "rna_fm_eval_gate.v1",
            "generated_at": now,
            "allow_fusion": False,
            "decision": "HOLD",
            "reason": f"checkpoint present but smoke failed: {type(e).__name__}: {e}",
            "checkpoint": str(ckpt),
            "fusion_weight": 0.0,
        }
    write_gate(gate)
    return gate


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="RNA-FM fusion gate")
    ap.add_argument("--weight", type=float, default=DEFAULT_REAL_WEIGHT)
    args = ap.parse_args(argv)
    gate = run_rna_fm_gate(fusion_weight=float(args.weight))
    print(json.dumps(gate, indent=2, ensure_ascii=False))
    return 0 if gate.get("decision") in ("PROMOTE", "HOLD") else 1


if __name__ == "__main__":
    raise SystemExit(main())
