# -*- coding: utf-8 -*-
"""RNA-FM fusion policy: mock → weights 0; real checkpoint + eval gate → may open."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from app.core.paths import REPORTS, ensure_artifact_dirs

GATE_NAME = "rna_fm_eval_gate.json"
DEFAULT_REAL_WEIGHT = 0.30


def checkpoint_path() -> Optional[Path]:
    raw = (os.environ.get("RNA_FM_CHECKPOINT") or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.exists() else None


def checkpoint_ready() -> bool:
    return checkpoint_path() is not None


def gate_path() -> Path:
    ensure_artifact_dirs()
    return REPORTS / GATE_NAME


def load_rna_fm_gate() -> dict[str, Any]:
    p = gate_path()
    if not p.is_file():
        return {"allow_fusion": False, "reason": "no rna_fm_eval_gate.json"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"allow_fusion": False}
    except Exception as e:
        return {"allow_fusion": False, "reason": f"gate unreadable: {type(e).__name__}"}


def apply_fusion_rna_policy(weights: dict[str, float]) -> dict[str, float]:
    """Force rna_* to 0 unless real checkpoint AND gate allow_fusion."""
    out = {str(k): float(v) for k, v in weights.items()}
    gate = load_rna_fm_gate()
    ready = checkpoint_ready()
    allow = bool(gate.get("allow_fusion")) and ready
    if not allow:
        out["rna_embed"] = 0.0
        out["rna_fm"] = 0.0
        return out
    w = gate.get("fusion_weight")
    try:
        w_f = float(w) if w is not None else DEFAULT_REAL_WEIGHT
    except (TypeError, ValueError):
        w_f = DEFAULT_REAL_WEIGHT
    w_f = max(0.0, min(1.0, w_f))
    out["rna_embed"] = w_f
    out["rna_fm"] = w_f
    return out


def write_gate(payload: dict[str, Any]) -> Path:
    ensure_artifact_dirs()
    p = gate_path()
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
