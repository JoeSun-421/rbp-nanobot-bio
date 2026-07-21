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
            from rbp_agent.core.runtime_config import load_runtime_config

            axes = (load_runtime_config().get("axes") or {})
        except Exception:
            return True, None
    if axes.get(axis) is False:
        return False, axis
    return True, None
