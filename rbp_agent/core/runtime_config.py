# -*- coding: utf-8 -*-
"""Load agent runtime config: evolved.yaml preferred when evolved: true."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from rbp_agent.core.paths import PACKAGE_ROOT

DEFAULT_CONFIG = PACKAGE_ROOT / "config" / "defaults.yaml"
EVOLVED_CONFIG = PACKAGE_ROOT / "config" / "evolved.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=4)
def load_runtime_config(*, prefer_evolved: bool = True) -> dict[str, Any]:
    """Return defaults merged with evolved overrides when available."""
    base = _load_yaml(DEFAULT_CONFIG)
    if not prefer_evolved:
        return dict(base)
    evo = _load_yaml(EVOLVED_CONFIG)
    if evo.get("evolved"):
        merged = {**base, **evo}
        # Deep-merge known nested maps
        for key in ("fusion_weights", "label_thresholds", "abstain_thresholds", "axes", "llm"):
            if isinstance(base.get(key), dict) or isinstance(evo.get(key), dict):
                merged[key] = {**(base.get(key) or {}), **(evo.get(key) or {})}
        return merged
    return dict(base)


def clear_runtime_config_cache() -> None:
    load_runtime_config.cache_clear()


def fusion_weights() -> dict[str, float]:
    cfg = load_runtime_config()
    raw = cfg.get("fusion_weights") or {}
    return {str(k): float(v) for k, v in raw.items()}


def label_thresholds() -> dict[str, float]:
    cfg = load_runtime_config()
    raw = cfg.get("label_thresholds") or {}
    defaults = {"strong": 0.75, "likely": 0.50, "unlikely": 0.25}
    out = dict(defaults)
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def tau_drop() -> float:
    cfg = load_runtime_config()
    try:
        return float(cfg.get("tau_drop", 0.30))
    except (TypeError, ValueError):
        return 0.30


def abstain_thresholds() -> dict[str, float]:
    """Per-metric floors for ``confidence_abstain`` (from evolved.yaml when set)."""
    cfg = load_runtime_config()
    raw = cfg.get("abstain_thresholds") or {}
    defaults = {
        "esmc_cosine": 0.55,
        "esm2_cosine": 0.55,
        "saprot_cosine": 0.55,
        "domain_jaccard": 0.5,
        "domain_overlap": 0.5,
        "seq_identity": 0.3,
        "tm_score": 0.5,
        "lddt": 0.5,
        "fused": 0.45,
    }
    out = dict(defaults)
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def config_source() -> str:
    """Human-readable which file is driving runtime (for doctor / logs)."""
    evo = _load_yaml(EVOLVED_CONFIG)
    if evo.get("evolved"):
        return str(EVOLVED_CONFIG)
    return str(DEFAULT_CONFIG)
