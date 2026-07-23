# -*- coding: utf-8 -*-
"""Model capability metadata from ``config/defaults.yaml`` ``models:`` section."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.paths import CACHE, REPORTS, ensure_artifact_dirs
from app.core.runtime_config import load_runtime_config


def model_specs() -> dict[str, dict[str, Any]]:
    cfg = load_runtime_config(prefer_evolved=False)
    raw = cfg.get("models") or {}
    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}


def probe_model_capabilities() -> dict[str, Any]:
    """Return ready/degraded/unavailable matrix without mutating delivery."""
    from app.backends.delivery.env import resolve_delivery_paths

    specs = model_specs()
    paths = resolve_delivery_paths()
    delivery = Path(paths["delivery_root"])
    matrix: dict[str, Any] = {}

    for name, spec in specs.items():
        entry: dict[str, Any] = {
            "tool": spec.get("tool"),
            "backend": spec.get("backend"),
            "status": "unknown",
            "reason": "",
        }
        backend = spec.get("backend")
        if backend == "delivery":
            env_name = spec.get("conda_env")
            if not delivery.is_dir():
                entry["status"] = "unavailable"
                entry["reason"] = "DELIVERY_ROOT missing"
            else:
                entry["status"] = "ready"
                entry["reason"] = f"delivery present; conda_env={env_name}"
                if name == "af3":
                    status_file = Path(__file__).resolve().parents[2] / ".af3_status"
                    first = ""
                    if status_file.is_file():
                        raw = status_file.read_text(encoding="utf-8", errors="replace")
                        for line in raw.splitlines():
                            if line.startswith("state="):
                                first = line.split("=", 1)[1].strip().lower()
                                break
                        entry["af3_status_file"] = first or "unknown"
                    if not (os.environ.get("AF3_PYTHON") or "").strip():
                        entry["status"] = "degraded"
                        entry["reason"] = "AF3_PYTHON unset; use AFDB/Foldseek fallback"
                    if first == "ok":
                        entry["status"] = "ready"
                        entry["reason"] = "AF3 probe ok"
                    elif first in ("deferred", "import_ok"):
                        entry["status"] = "degraded"
                        entry["reason"] = f".af3_status={first}; prefer AFDB"
                    elif first in ("broken", "missing"):
                        entry["status"] = "unavailable"
                        entry["reason"] = f".af3_status={first}; AFDB only"
                    elif not first and not (os.environ.get("AF3_PYTHON") or "").strip():
                        entry["status"] = "degraded"
                        entry["reason"] = "AF3_PYTHON unset; use AFDB/Foldseek fallback"
                if name == "esm_c":
                    entry["cache"] = str(CACHE / "esm")
        elif backend == "agent_local":
            ckpt_env = str(spec.get("checkpoint_env") or "")
            ckpt = (os.environ.get(ckpt_env) or "").strip() if ckpt_env else ""
            if ckpt and Path(ckpt).exists():
                entry["status"] = "ready"
                entry["reason"] = f"{ckpt_env} set"
                entry["mode"] = "real"
            else:
                entry["status"] = "degraded"
                entry["reason"] = "mock k-mer embedder (fusion weights rna_*=0)"
                entry["mode"] = "mock"
        else:
            entry["status"] = "unknown"
            entry["reason"] = f"backend={backend}"
        matrix[name] = entry

    return {
        "models": matrix,
        "n_ready": sum(1 for v in matrix.values() if v.get("status") == "ready"),
        "n_degraded": sum(1 for v in matrix.values() if v.get("status") == "degraded"),
        "n_unavailable": sum(1 for v in matrix.values() if v.get("status") == "unavailable"),
    }


def write_capability_matrix(path: Path | None = None) -> Path:
    ensure_artifact_dirs()
    out = path or (REPORTS / "model_capability_matrix.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    data = probe_model_capabilities()
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
