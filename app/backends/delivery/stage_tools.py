# -*- coding: utf-8 -*-
"""Stage tool subsets + axes → tool hard-gates (mature agent allowlists)."""

from __future__ import annotations

from typing import Optional

# Curated + whitelist tools grouped by playbook stage (SKILL.md).
# Used for docs, optional filtering, and axis gating — not a second registry.
STAGE_TOOL_SETS: dict[str, frozenset[str]] = {
    "stage0": frozenset(
        {
            "resolve_rbp",
            "get_known_rbp_list",
            "predict_interaction",
            "rna_preprocess",
        }
    ),
    "stage1": frozenset(
        {
            "lookup_proxy_cache",
            "seq_similarity",
            "rna_similarity",
            "get_func_annotation",
            "domain_architecture",
            "structure_fetch",
            "struct_similarity",
            "predict_structure",
            "literature_search",
            "fuse_similarity_views",
        }
    ),
    "stage2": frozenset({"predict_interaction"}),
    "stage3": frozenset(
        {
            "transfer_prior_lookup",
            "donor_quality_prior",
            "similarity_weighted_vote",
            "confidence_abstain",
        }
    ),
}

# Map delivery/curated tool name → runtime_config axes.* key that must be true.
# Tools not listed are always allowed (subject to whitelist).
TOOL_AXIS_GATE: dict[str, str] = {
    "seq_similarity": "sequence",
    "struct_similarity": "structure",
    "structure_fetch": "structure",
    "predict_structure": "use_af3",
    "domain_architecture": "domain",
    "get_func_annotation": "function_annotation",
    "literature_search": "literature",
}


def axis_enabled(tool_name: str, axes: Optional[dict] = None) -> tuple[bool, Optional[str]]:
    """Return (allowed, blocking_axis_or_None)."""
    axis = TOOL_AXIS_GATE.get(tool_name)
    if not axis:
        return True, None
    if axes is None:
        try:
            from app.core.runtime_config import load_runtime_config

            axes = (load_runtime_config().get("axes") or {})
        except Exception:
            return True, None
    if axes.get(axis) is False:
        return False, axis
    return True, None


# Product-required axes for multi-view MVP (AF3 intentionally optional).
REQUIRED_AXES_ON: tuple[str, ...] = (
    "embedding",
    "sequence",
    "domain",
    "structure",
    "function_annotation",
    "rna_blastn",
    "literature",
)
OPTIONAL_AXES_OFF_OK: tuple[str, ...] = (
    "use_af3",
    "struct_align_refine",
)


def assert_full_axes_enabled(axes: Optional[dict] = None) -> list[str]:
    """Return list of required axes that are off (empty ⇒ multi-view OK).

    ``use_af3`` may stay false (AFDB preferred). Does not raise.
    """
    if axes is None:
        try:
            from app.core.runtime_config import load_runtime_config

            axes = dict(load_runtime_config().get("axes") or {})
        except Exception:
            axes = {}
    off: list[str] = []
    for key in REQUIRED_AXES_ON:
        if axes.get(key) is False:
            off.append(key)
    return off


def axis_status_matrix(axes: Optional[dict] = None) -> dict[str, str]:
    """Per-axis ready|off|degraded (AF3 reads ``.af3_status`` when enabled)."""
    if axes is None:
        try:
            from app.core.runtime_config import load_runtime_config

            axes = dict(load_runtime_config().get("axes") or {})
        except Exception:
            axes = {}
    out: dict[str, str] = {}
    for key, val in sorted(axes.items()):
        if val is False:
            out[key] = "off"
            continue
        if key == "use_af3":
            out[key] = _af3_runtime_status()
        else:
            out[key] = "ready"
    return out


def _af3_runtime_status() -> str:
    """Map host ``.af3_status`` + AF3_PYTHON to ready|degraded|off."""
    import os
    from pathlib import Path

    status_file = Path(__file__).resolve().parents[3] / ".af3_status"
    first = ""
    if status_file.is_file():
        raw = status_file.read_text(encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            if line.startswith("state="):
                first = line.split("=", 1)[1].strip().lower()
                break
    if first == "ok":
        return "ready"
    if first in ("deferred", "import_ok"):
        return "degraded"
    if first in ("broken", "missing"):
        return "off"
    if not (os.environ.get("AF3_PYTHON") or "").strip():
        return "degraded"
    return "ready"
