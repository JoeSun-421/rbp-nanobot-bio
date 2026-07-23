# -*- coding: utf-8 -*-
"""Stage-0 helper — check_near_known (seq identity ≥ near_match threshold)."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import (
    dumps,
    err,
    get_delivery_client,
    looks_like_rna,
    ok,
    resolve_protein_sequence,
    timed_call,
)


def _near_threshold() -> float:
    try:
        from app.core.runtime_config import load_runtime_config

        return float(load_runtime_config().get("near_match_seq_identity") or 0.95)
    except Exception:
        return 0.95


def _score_as_identity(hit: dict[str, Any]) -> Optional[float]:
    """Normalize hit score to [0,1] identity when metric looks like identity."""
    try:
        from app.core.verdict_schema import is_near_match_score
    except Exception:
        is_near_match_score = None  # type: ignore

    score = hit.get("score")
    if score is None:
        score = hit.get("identity")
    if score is None:
        return None
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    metric = str(hit.get("metric") or hit.get("method") or "").lower()
    # Prefer explicit identity-like metrics; ESM cosine is not %id.
    if metric and any(
        x in metric for x in ("ident", "mmseqs", "seq_id", "pident", "blast")
    ):
        if s > 1.0 + 1e-9:
            return s / 100.0
        return s
    if not metric or metric in ("seq_identity", "identity"):
        if s > 1.0 + 1e-9:
            return s / 100.0
        # Ambiguous 0–1: treat as identity only if already near threshold helper agrees
        if is_near_match_score and is_near_match_score(s, 0.90):
            return s if s <= 1.0 else s / 100.0
    return None


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "sequence": {"type": "string"},
            "uniprot": {"type": "string"},
            "alias": {"type": "string"},
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 5},
            "threshold": {
                "type": "number",
                "description": "Override near_match_seq_identity (default 0.95).",
            },
        },
        "required": [],
    }
)
class CheckNearKnownTool(Tool):
    """Read-only Stage-0 near-known detector (Proposal ≥95% identity Fast Path)."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "check_near_known"

    @property
    def description(self) -> str:
        return (
            "Near-known Fast Path check: MMseqs seq identity vs catalogue. "
            "If best identity ≥ 0.95 to a headed RBP, return near_match=true + "
            "donor alias — then predict_interaction once on that donor and STOP. "
            "Read-only; does not invent scores."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        try:
            from nanobot.agent.tools.rbp.turn_guards import blocked_envelope_json

            blocked = blocked_envelope_json(self.name)
            if blocked:
                return blocked
        except Exception:
            pass
        raw = (kwargs.get("sequence") or "").strip()
        if raw and looks_like_rna(raw):
            return dumps(err("sequence looks like RNA; pass protein AA / alias / uniprot"))
        seq, src = resolve_protein_sequence(kwargs)
        if not seq:
            return dumps(
                err(
                    "need alias/uniprot or protein AA sequence for near-known check"
                )
            )
        thr = kwargs.get("threshold")
        threshold = float(thr) if thr is not None else _near_threshold()

        def _run():
            client = get_delivery_client()
            mm = client.call(
                "protein_seq_similarity",
                {"sequence": seq, "top_k": int(kwargs.get("top_k") or 5)},
            )
            if mm.get("error") and not mm.get("hits"):
                raise RuntimeError(mm.get("error") or "protein_seq_similarity failed")
            hits = list(mm.get("hits") or [])
            best: Optional[dict[str, Any]] = None
            best_id = -1.0
            for h in hits:
                if not isinstance(h, dict):
                    continue
                ident = _score_as_identity(h)
                if ident is None:
                    continue
                if ident > best_id:
                    best_id = ident
                    best = h
            near = bool(best is not None and best_id >= threshold)
            donor_alias = None
            donor_uniprot = None
            if best is not None:
                donor_alias = best.get("alias") or best.get("rbp_id") or best.get("name")
                donor_uniprot = best.get("uniprot") or best.get("rbp_id")
            # Prefer headed donors when claiming near_match
            headed = False
            if near and donor_alias:
                try:
                    from nanobot.agent.tools.rbp.turn_guards import alias_has_panel_head

                    headed = alias_has_panel_head(str(donor_alias))
                    if not headed and donor_uniprot:
                        headed = alias_has_panel_head(str(donor_uniprot))
                except Exception:
                    headed = True  # delivery hit implies catalogue; soft
            if near and not headed:
                near = False
            out = {
                "near_match": near,
                "threshold": threshold,
                "best_identity": best_id if best_id >= 0 else None,
                "donor_alias": str(donor_alias) if near and donor_alias else None,
                "donor_uniprot": str(donor_uniprot) if near and donor_uniprot else None,
                "headed": headed if best is not None else False,
                "hits": hits[:5],
                "sequence_source": src,
                "hint": (
                    "near_match: call predict_interaction once on donor_alias then STOP"
                    if near
                    else "not near-known; continue characterize → parallel retrieve → fuse → abstain → predict"
                ),
            }
            if near:
                try:
                    from nanobot.agent.tools.rbp.turn_guards import add_evidence_flag

                    add_evidence_flag("near_match", True)
                    add_evidence_flag("near_match_donor", out["donor_alias"])
                except Exception:
                    pass
            return out

        value, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        if error:
            return dumps(err(error, ms))
        return dumps(ok(value, ms))
