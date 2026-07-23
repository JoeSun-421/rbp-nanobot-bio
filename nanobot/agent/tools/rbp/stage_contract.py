# -*- coding: utf-8 -*-
"""Stage 0–3 contract — single source of truth for tool ordering (Proposal §5/§9).

This module replaces the scattered hardcoded tool-name sets that previously lived
in ``turn_guards`` with a declarative contract:

* ``STAGE_RETRIEVE`` — Stage-1 retrieve tools. These are ``concurrency_safe``
  (``read_only=True``), so the nanobot runner batches consecutive calls into a
  single ``asyncio.gather`` → true parallel four-view retrieval.
* ``REQUIRES`` — serial edges on the unseen/transfer path. Each entry says the
  key tool may only execute after the listed prerequisite tools have been
  marked done this turn. ``turn_guards`` consults this map instead of hardcoding
  the fuse → abstain → predict chain.
* ``OWN_HEAD_STOP_BLOCKED`` — tools refused after a successful own-head
  ``predict_interaction`` (Stage 0 STOP: emit verdict, do not retrieve/transfer).

The contract is data-driven so a future runner-level scheduler can consume the
same edges (B2: scheduling-layer prevention, not just post-hoc guard blocking).
"""

from __future__ import annotations

from typing import Any, Optional

# Stage-1 retrieve tools (parallel-safe; runner batches them when emitted
# consecutively in one assistant turn). Curated + raw delivery retrieve tools.
STAGE_RETRIEVE: frozenset[str] = frozenset(
    {
        # curated retrieve
        "seq_similarity",
        "rna_similarity",
        "struct_similarity",
        "get_func_annotation",
        "predict_structure",
        "literature_search",
        "check_near_known",
        "lookup_proxy_cache",
        # raw delivery retrieve extras (whitelist)
        "structure_fetch",
        "structure_consensus",
        "rna_blastn",
        "domain_architecture",
        "function_category",
        "go_pfam_lookup",
        "pdb_metadata",
        "colabfold_msa",
        "esm_embed",
        "pymol_util",
        "rna_preprocess",
    }
)

# Serial prerequisite edges on the unseen/transfer path.
#   key tool -> tuple of prerequisite tool names that must be done first.
# Special sentinel "__any_retrieve__" means "at least one STAGE_RETRIEVE tool".
REQUIRES: dict[str, tuple[str, ...]] = {
    "fuse_similarity_views": ("__any_retrieve__",),
    "confidence_abstain": ("fuse_similarity_views",),
    "transfer_prior_lookup": ("fuse_similarity_views",),
    "donor_quality_prior": ("fuse_similarity_views",),
    "similarity_weighted_vote": ("confidence_abstain",),
    # predict_interaction on the transfer/multi-donor path requires abstain.
    # Own-head single-alias path is exempt (handled in turn_guards).
    "predict_interaction": ("confidence_abstain",),
}

# Tools refused after own-head predict_interaction success (Stage 0 STOP).
OWN_HEAD_STOP_BLOCKED: frozenset[str] = frozenset(
    STAGE_RETRIEVE
    | {
        "fuse_similarity_views",
        "transfer_prior_lookup",
        "donor_quality_prior",
        "similarity_weighted_vote",
        "confidence_abstain",
        "predict_structure_af3",
        "literature_retrieval",
        "esm_similarity",
        "protein_seq_similarity",
        "struct_similarity_foldseek",
        "struct_align_usalign",
    }
)


def is_retrieve(tool_name: str) -> bool:
    return tool_name in STAGE_RETRIEVE


def prerequisite_for(tool_name: str) -> Optional[tuple[str, ...]]:
    return REQUIRES.get(tool_name)


def describe_unmet_prerequisite(tool_name: str, done: set[str]) -> Optional[str]:
    """Return a human reason if ``tool_name`` has unmet prerequisites, else None.

    ``done`` is the set of tool names already completed this turn.
    """
    prereqs = REQUIRES.get(tool_name)
    if not prereqs:
        return None
    for p in prereqs:
        if p == "__any_retrieve__":
            if not (done & STAGE_RETRIEVE):
                return (
                    f"Call at least one retrieve tool ({sorted(STAGE_RETRIEVE)[:4]}...) "
                    f"before {tool_name}."
                )
        elif p not in done:
            return f"Call {p} before {tool_name}. BUILD_SPEC stage order."
    return None


def is_acyclic() -> bool:
    """Sanity: REQUIRES edges must not form a cycle (excludes the sentinel)."""
    graph: dict[str, list[str]] = {
        k: [p for p in v if p != "__any_retrieve__"] for k, v in REQUIRES.items()
    }
    color: dict[str, int] = {}

    def dfs(node: str) -> bool:
        color[node] = 1
        for nxt in graph.get(node, []):
            if color.get(nxt) == 1:
                return False
            if color.get(nxt, 0) == 0 and not dfs(nxt):
                return False
        color[node] = 2
        return True

    return all(dfs(n) for n in list(graph) if color.get(n, 0) == 0)


__all__ = [
    "STAGE_RETRIEVE",
    "REQUIRES",
    "OWN_HEAD_STOP_BLOCKED",
    "is_retrieve",
    "prerequisite_for",
    "describe_unmet_prerequisite",
    "is_acyclic",
]
