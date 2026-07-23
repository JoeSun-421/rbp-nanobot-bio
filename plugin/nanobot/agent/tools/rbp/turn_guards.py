# -*- coding: utf-8 -*-
"""Per-turn Stage 0–3 hard guards (Proposal §9; SKILL alone is not enough)."""

from __future__ import annotations

from typing import Any, Optional

# After successful own-head predict, retrieve / transfer tools must refuse.
_OWN_HEAD_STOP: bool = False

# Unseen path: fuse → confidence_abstain → predict (BUILD_SPEC §4).
_FUSE_DONE: bool = False
_ABSTAIN_DONE: bool = False

# Accumulated evidence flags for Stage-3 normalize_verdict (tool-sourced).
_EVIDENCE_FLAGS: dict[str, Any] = {}

# Tools blocked after own-head success (Stage 0 STOP).
RETRIEVE_AFTER_OWN_HEAD: frozenset[str] = frozenset(
    {
        "seq_similarity",
        "rna_similarity",
        "struct_similarity",
        "structure_fetch",
        "predict_structure",
        "structure_predict_af3",
        "domain_architecture",
        "get_func_annotation",
        "literature_search",
        "literature_retrieval",
        "lookup_proxy_cache",
        "fuse_similarity_views",
        "transfer_prior_lookup",
        "donor_quality_prior",
        "similarity_weighted_vote",
        "confidence_abstain",
        "check_near_known",
        "rna_blastn",
        "colabfold_msa",
        "structure_consensus",
        "function_category",
        "esm_embed",
        "esm_similarity",
        "protein_seq_similarity",
        "go_pfam_lookup",
        "pdb_metadata",
        "pymol_util",
        "struct_similarity_foldseek",
        "struct_align_usalign",
    }
)


def reset_stage_guards() -> None:
    global _OWN_HEAD_STOP, _FUSE_DONE, _ABSTAIN_DONE, _EVIDENCE_FLAGS
    _OWN_HEAD_STOP = False
    _FUSE_DONE = False
    _ABSTAIN_DONE = False
    _EVIDENCE_FLAGS = {}


def mark_own_head_success() -> None:
    global _OWN_HEAD_STOP
    _OWN_HEAD_STOP = True


def mark_fuse_done() -> None:
    global _FUSE_DONE
    _FUSE_DONE = True


def mark_abstain_done() -> None:
    global _ABSTAIN_DONE
    _ABSTAIN_DONE = True
    add_evidence_flag("abstain_called", True)


def fuse_done() -> bool:
    return bool(_FUSE_DONE)


def abstain_done() -> bool:
    return bool(_ABSTAIN_DONE)


def own_head_stop_active() -> bool:
    return bool(_OWN_HEAD_STOP)


def add_evidence_flag(key: str, value: Any = True) -> None:
    _EVIDENCE_FLAGS[str(key)] = value


def evidence_flags() -> dict[str, Any]:
    return dict(_EVIDENCE_FLAGS)


def retrieve_blocked_reason(tool_name: str) -> Optional[str]:
    if _OWN_HEAD_STOP and tool_name in RETRIEVE_AFTER_OWN_HEAD:
        return (
            f"Stage 0 STOP: own-head predict_interaction already succeeded this turn; "
            f"refusing {tool_name}. Emit JSON verdict now (do not retrieve/transfer)."
        )
    return None


def transfer_predict_blocked_reason(
    *,
    force_transfer: bool,
    rbps: list[str],
    cohort: str = "K562",
) -> Optional[str]:
    """Block donor/transfer predict until confidence_abstain after fuse (when enabled)."""
    if _OWN_HEAD_STOP:
        return None
    rbps_list = [str(x) for x in rbps]
    # Own-head eligible single alias: no abstain gate
    if not force_transfer and len(rbps_list) == 1 and alias_has_panel_head(
        rbps_list[0], cohort=cohort
    ):
        return None
    # Transfer / multi-donor path
    try:
        from app.core.runtime_config import load_runtime_config

        integ = load_runtime_config().get("integrate") or {}
        if integ.get("use_abstain") is False:
            return None
    except Exception:
        pass
    if not _ABSTAIN_DONE:
        return (
            "Transfer path: call confidence_abstain after fuse "
            "(prefer hits_emb / embedding hits) before predict_interaction. "
            "BUILD_SPEC: fuse → abstain → predict."
        )
    return None


def blocked_envelope_json(tool_name: str) -> Optional[str]:
    """JSON error envelope if Stage-0 stop blocks ``tool_name``, else None."""
    reason = retrieve_blocked_reason(tool_name)
    if not reason:
        return None
    from nanobot.agent.tools.rbp.common import dumps, err

    return dumps(err(reason))


def alias_has_panel_head(query: str, *, cohort: str = "K562") -> bool:
    """True if ``query`` resolves to a catalogue RBP with a RhoBind head."""
    q = (query or "").strip()
    if not q:
        return False
    try:
        from app.backends.delivery.env import apply_delivery_env, load_rbp_registry

        apply_delivery_env()
        reg = load_rbp_registry()
    except Exception:
        return False
    q_up = q.upper()
    for up, rec in reg.items():
        if not isinstance(rec, dict):
            continue
        alias = str(rec.get("alias") or "").upper()
        if q_up not in (str(up).upper(), alias):
            continue
        heads = rec.get("head_index") or {}
        if isinstance(heads, dict) and heads.get(cohort) is not None:
            return True
        if heads:  # any cohort head counts as in-panel
            return True
    return False
