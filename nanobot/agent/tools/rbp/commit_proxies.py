# -*- coding: utf-8 -*-
"""Stage-1 Checkpoint 1 — commit LLM-calibrated proxy candidates (proposal §4).

Deterministic ``fuse_similarity_views`` remains the numeric *evidence* baseline.
Authoritative ``s_i`` for Stage 2/3 comes from the LLM via this tool.
"""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import dumps, err, ok


def _normalize_candidate(row: dict[str, Any], *, tau_drop: float) -> dict[str, Any] | None:
    rid = (
        row.get("rbp_id")
        or row.get("uniprot")
        or row.get("alias")
        or row.get("donor")
    )
    if not rid:
        return None
    try:
        sim = float(row.get("similarity_score"))
    except (TypeError, ValueError):
        return None
    if sim < float(tau_drop):
        return None
    br = row.get("similarity_breakdown")
    if not isinstance(br, dict):
        br = {}
    # Normalize breakdown keys to proposal {seq, struct, func}
    mapped: dict[str, float] = {}
    for k, v in br.items():
        key = str(k).lower()
        if key in ("seq", "sequence", "esmc_cosine", "esm2_cosine", "seq_identity"):
            mapped["seq"] = max(mapped.get("seq", 0.0), float(v))
        elif key in ("struct", "structure", "tm_score", "lddt", "fident"):
            mapped["struct"] = max(mapped.get("struct", 0.0), float(v))
        elif key in (
            "func",
            "function",
            "domain_jaccard",
            "domain_overlap",
            "function_similarity",
        ):
            mapped["func"] = max(mapped.get("func", 0.0), float(v))
        else:
            mapped[key] = float(v)
    rationale = str(row.get("rationale") or "").strip()
    out = {
        "rbp_id": str(rid),
        "alias": str(row.get("alias") or rid),
        "similarity_score": round(sim, 4),
        "similarity_breakdown": {k: round(v, 4) for k, v in mapped.items()},
        "rationale": rationale
        or "LLM-calibrated similarity (proposal §4 Checkpoint 1)",
    }
    if row.get("uniprot"):
        out["uniprot"] = str(row["uniprot"])
    return out


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "description": (
                    "LLM-calibrated proxy list (proposal §4). Each item: "
                    "rbp_id, similarity_score∈[0,1], similarity_breakdown"
                    "{seq,struct,func}, rationale. Scores below τ_drop are dropped."
                ),
                "items": {"type": "object"},
            },
            "tau_drop": {
                "type": "number",
                "description": "Drop candidates with similarity_score below this "
                "(default from config, usually 0.30).",
            },
            "n_cand": {
                "type": "integer",
                "description": "Max candidates to keep (default from config, usually 5).",
            },
        },
        "required": ["candidates"],
    }
)
class CommitProxyCandidatesTool(Tool):
    """Persist LLM-calibrated Stage-1 proxies for Stage 2/3 (authoritative s_i)."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "commit_proxy_candidates"

    @property
    def description(self) -> str:
        return (
            "Checkpoint 1 (proposal §4): after fuse_similarity_views, commit the "
            "LLM-calibrated proxy list (≤ n_cand, drop < τ_drop) with "
            "similarity_score + similarity_breakdown {seq,struct,func} + rationale. "
            "Required on the unseen/transfer path before confidence_abstain / "
            "predict_interaction. Deterministic fuse scores are evidence only — "
            "these committed scores are the authoritative s_i for Stage 3."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        try:
            from nanobot.agent.tools.rbp.turn_guards import (
                blocked_envelope_json,
                commit_blocked_reason,
            )

            blocked = blocked_envelope_json(self.name)
            if blocked:
                return blocked
            reason = commit_blocked_reason()
            if reason:
                return dumps(err(reason))
        except Exception:
            pass

        raw = kwargs.get("candidates")
        if not isinstance(raw, list) or not raw:
            return dumps(err("candidates must be a non-empty list of proxy objects"))

        try:
            from nanobot.agent.tools.rbp.common import get_runtime_config

            cfg = get_runtime_config()
        except Exception:
            cfg = {}
        tau = kwargs.get("tau_drop")
        tau_f = float(tau) if tau is not None else float(cfg.get("tau_drop") or 0.30)
        n_cand = kwargs.get("n_cand")
        n_max = int(n_cand) if n_cand is not None else int(cfg.get("n_cand") or 5)

        normalized: list[dict[str, Any]] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            item = _normalize_candidate(row, tau_drop=tau_f)
            if item:
                normalized.append(item)
        normalized.sort(key=lambda x: x["similarity_score"], reverse=True)
        kept = normalized[:n_max]
        if not kept:
            return dumps(
                err(
                    f"no candidates survived τ_drop={tau_f}; "
                    "re-run Checkpoint 1 with higher LLM-calibrated scores or "
                    "broader retrieve"
                )
            )

        try:
            from nanobot.agent.tools.rbp.turn_guards import set_committed_proxies

            set_committed_proxies(kept)
        except Exception as exc:
            return dumps(err(f"failed to persist committed proxies: {exc}"))

        return dumps(
            ok(
                {
                    "candidates": kept,
                    "n": len(kept),
                    "tau_drop": tau_f,
                    "n_cand": n_max,
                    "authoritative": True,
                    "next": "confidence_abstain on hits_emb, then predict_interaction "
                    "on committed donor aliases",
                }
            )
        )
