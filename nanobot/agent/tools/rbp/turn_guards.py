# -*- coding: utf-8 -*-
"""Per-turn Stage 0–3 hard guards (Proposal §9; SKILL alone is not enough).

The serial Stage-2/3 contract (fuse → abstain → predict) and the Stage-0 STOP
tool set are declared in :mod:`stage_contract` (single source of truth). This
module holds the per-turn *state* (flags + evidence) and the runtime checks
that consult the contract. A future runner-level scheduler can consume
``stage_contract.REQUIRES`` directly; until then these guards are the
scheduling-layer prevention that keeps the LLM from calling integrate tools
out of order (B2: dependency declaration, not just post-hoc blocking).
"""

from __future__ import annotations

from typing import Any, Optional

from nanobot.agent.tools.rbp.stage_contract import (
    OWN_HEAD_STOP_BLOCKED,
    REQUIRES,
    STAGE_RETRIEVE,
    describe_unmet_prerequisite,
)

# After successful own-head predict, retrieve / transfer tools must refuse.
_OWN_HEAD_STOP: bool = False
# Unseen path: fuse → commit_proxy_candidates → confidence_abstain → predict (§4).
_FUSE_DONE: bool = False
_COMMIT_DONE: bool = False
_ABSTAIN_DONE: bool = False

# Accumulated evidence flags for Stage-3 normalize_verdict (tool-sourced).
_EVIDENCE_FLAGS: dict[str, Any] = {}
# LLM-calibrated proxies from commit_proxy_candidates (authoritative s_i).
_COMMITTED_PROXIES: list[dict[str, Any]] = []

# Tools blocked after own-head success (Stage 0 STOP) — declared in stage_contract.
RETRIEVE_AFTER_OWN_HEAD: frozenset[str] = OWN_HEAD_STOP_BLOCKED


def reset_stage_guards() -> None:
    global _OWN_HEAD_STOP, _FUSE_DONE, _COMMIT_DONE, _ABSTAIN_DONE
    global _EVIDENCE_FLAGS, _COMMITTED_PROXIES
    _OWN_HEAD_STOP = False
    _FUSE_DONE = False
    _COMMIT_DONE = False
    _ABSTAIN_DONE = False
    _EVIDENCE_FLAGS = {}
    _COMMITTED_PROXIES = []
    _RETRIEVE_DONE.clear()


def mark_own_head_success() -> None:
    global _OWN_HEAD_STOP
    _OWN_HEAD_STOP = True


def mark_fuse_done() -> None:
    global _FUSE_DONE
    _FUSE_DONE = True


def mark_commit_done() -> None:
    global _COMMIT_DONE
    _COMMIT_DONE = True


def set_committed_proxies(proxies: list[dict[str, Any]]) -> None:
    """Store LLM-calibrated proxies and mark Checkpoint 1 complete."""
    global _COMMITTED_PROXIES
    _COMMITTED_PROXIES = [dict(p) for p in proxies if isinstance(p, dict)]
    mark_commit_done()
    add_evidence_flag("llm_calibrated_proxies", True)
    add_evidence_flag("n_committed_proxies", len(_COMMITTED_PROXIES))


def committed_proxies() -> list[dict[str, Any]]:
    return [dict(p) for p in _COMMITTED_PROXIES]


def mark_abstain_done() -> None:
    global _ABSTAIN_DONE
    _ABSTAIN_DONE = True
    add_evidence_flag("abstain_called", True)


def fuse_done() -> bool:
    return bool(_FUSE_DONE)


def commit_done() -> bool:
    return bool(_COMMIT_DONE)


def abstain_done() -> bool:
    return bool(_ABSTAIN_DONE)


def own_head_stop_active() -> bool:
    return bool(_OWN_HEAD_STOP)


def add_evidence_flag(key: str, value: Any = True) -> None:
    _EVIDENCE_FLAGS[str(key)] = value


def evidence_flags() -> dict[str, Any]:
    return dict(_EVIDENCE_FLAGS)


def _done_set() -> set[str]:
    """Tools marked done this turn, for prerequisite checks."""
    done: set[str] = set()
    if _FUSE_DONE:
        done.add("fuse_similarity_views")
    if _COMMIT_DONE:
        done.add("commit_proxy_candidates")
    if _ABSTAIN_DONE:
        done.add("confidence_abstain")
    return done


# Retrieve tool names observed done this turn (for the fuse ``__any_retrieve__``
# edge). Populated by retrieve tools calling ``mark_retrieve_done``.
_RETRIEVE_DONE: set[str] = set()


def mark_retrieve_done(tool_name: str) -> None:
    if tool_name in STAGE_RETRIEVE:
        _RETRIEVE_DONE.add(tool_name)


def _any_retrieve_done() -> bool:
    return bool(_RETRIEVE_DONE)


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
    """Block donor/transfer predict until fuse → commit → abstain (when enabled).

    The edges are declared in :mod:`stage_contract` (``REQUIRES``); the messages
    below surface the earliest unmet prerequisite in stage order so the LLM gets
    the same guidance the contract encodes.
    """
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
        from nanobot.agent.tools.rbp.common import get_runtime_config

        integ = get_runtime_config().get("integrate") or {}
        if integ.get("use_abstain") is False:
            return None
    except Exception:
        pass
    # Data-driven: only enforce edges that stage_contract declares.
    predict_reqs = REQUIRES.get("predict_interaction", ())
    abstain_reqs = REQUIRES.get("confidence_abstain", ())
    commit_reqs = REQUIRES.get("commit_proxy_candidates", ())
    if "fuse_similarity_views" in commit_reqs and not _FUSE_DONE:
        return (
            "Transfer path: call fuse_similarity_views before "
            "commit_proxy_candidates / confidence_abstain / predict_interaction. "
            "Proposal §4: fuse → commit → abstain → predict."
        )
    if "commit_proxy_candidates" in abstain_reqs and not _COMMIT_DONE:
        return (
            "Transfer path: call commit_proxy_candidates after fuse "
            "(LLM-calibrated similarity_score + breakdown) before "
            "confidence_abstain / predict_interaction. "
            "Proposal §4 Checkpoint 1."
        )
    if "fuse_similarity_views" in abstain_reqs and not _FUSE_DONE:
        return (
            "Transfer path: call fuse_similarity_views before confidence_abstain / "
            "predict_interaction. BUILD_SPEC: fuse → abstain → predict."
        )
    if "confidence_abstain" in predict_reqs and not _ABSTAIN_DONE:
        return (
            "Transfer path: call confidence_abstain after commit "
            "(prefer hits_emb / embedding hits) before predict_interaction. "
            "Proposal §4: fuse → commit → abstain → predict."
        )
    return None


def abstain_blocked_reason() -> Optional[str]:
    """Block confidence_abstain until fuse + commit on the unseen/transfer path."""
    if _OWN_HEAD_STOP:
        return (
            "Stage 0 STOP: own-head already succeeded; refuse confidence_abstain. "
            "Emit JSON verdict now."
        )
    abstain_reqs = REQUIRES.get("confidence_abstain", ())
    if "commit_proxy_candidates" in abstain_reqs and not _COMMIT_DONE:
        return (
            "Call commit_proxy_candidates (LLM-calibrated proxies) before "
            "confidence_abstain. Proposal §4: fuse → commit → abstain → predict."
        )
    if "fuse_similarity_views" in abstain_reqs and not _FUSE_DONE:
        return (
            "Call fuse_similarity_views before confidence_abstain. "
            "BUILD_SPEC: fuse → abstain → predict."
        )
    return None


def commit_blocked_reason() -> Optional[str]:
    """Block commit_proxy_candidates until fuse on the unseen path."""
    if _OWN_HEAD_STOP:
        return (
            "Stage 0 STOP: own-head already succeeded; refuse commit_proxy_candidates. "
            "Emit JSON verdict now."
        )
    commit_reqs = REQUIRES.get("commit_proxy_candidates", ())
    if "fuse_similarity_views" in commit_reqs and not _FUSE_DONE:
        return (
            "Call fuse_similarity_views before commit_proxy_candidates. "
            "Proposal §4: fuse (evidence) → LLM commit (authoritative s_i)."
        )
    return None


def fuse_blocked_reason() -> Optional[str]:
    """Block fuse_similarity_views until at least one retrieve tool has run.

    Soft guard: only surfaces when the contract declares the ``__any_retrieve__``
    edge AND no retrieve tool has been called this turn. Not wired as a hard
    block by default (the SKILL guides ordering); available for stricter modes.
    """
    if _OWN_HEAD_STOP:
        return (
            "Stage 0 STOP: own-head already succeeded; refuse fuse_similarity_views. "
            "Emit JSON verdict now."
        )
    fuse_reqs = REQUIRES.get("fuse_similarity_views", ())
    if "__any_retrieve__" in fuse_reqs and not _any_retrieve_done():
        return (
            "Call at least one retrieve tool (seq_similarity / rna_similarity / "
            "struct_similarity / structure_fetch / get_func_annotation) before "
            "fuse_similarity_views."
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
        from nanobot.agent.tools.rbp.common import (
            apply_delivery_env_facade,
            load_rbp_registry_facade,
        )

        apply_delivery_env_facade()
        reg = load_rbp_registry_facade()
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


__all__ = [
    "RETRIEVE_AFTER_OWN_HEAD",
    "STAGE_RETRIEVE",
    "reset_stage_guards",
    "mark_own_head_success",
    "mark_fuse_done",
    "mark_commit_done",
    "set_committed_proxies",
    "committed_proxies",
    "mark_abstain_done",
    "mark_retrieve_done",
    "fuse_done",
    "commit_done",
    "abstain_done",
    "own_head_stop_active",
    "add_evidence_flag",
    "evidence_flags",
    "retrieve_blocked_reason",
    "transfer_predict_blocked_reason",
    "abstain_blocked_reason",
    "commit_blocked_reason",
    "fuse_blocked_reason",
    "blocked_envelope_json",
    "alias_has_panel_head",
]
