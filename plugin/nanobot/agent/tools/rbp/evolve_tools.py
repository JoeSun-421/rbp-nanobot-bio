# -*- coding: utf-8 -*-
"""Self-evolution runtime tools: proxy cache lookup + multi-view fusion."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import dumps, err, ok


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Target RBP gene symbol (e.g. NSUN2).",
            },
            "uniprot": {
                "type": "string",
                "description": "Target UniProt accession.",
            },
            "min_hits": {
                "type": "integer",
                "default": 2,
                "description": "Minimum promotions before cache is trusted.",
            },
        },
        "required": [],
    }
)
class LookupProxyCacheTool(Tool):
    """Bypass Stage 1 when (p* → proxies) has been promoted."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "lookup_proxy_cache"

    @property
    def description(self) -> str:
        return (
            "Look up promoted proxy donors for an unseen RBP from the offline "
            "self-evolution cache. On hit, skip Stage 1 multi-view retrieval and "
            "predict with returned proxies. Call after resolve_rbp when in_panel=false."
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
        def _run():
            from rbp_eval.proxy_cache import lookup_proxies

            alias = (kwargs.get("alias") or "").strip() or None
            uniprot = (kwargs.get("uniprot") or "").strip() or None
            if not alias and not uniprot:
                return err("provide alias and/or uniprot")
            proxies = lookup_proxies(
                alias=alias,
                uniprot=uniprot,
                min_hits=int(kwargs.get("min_hits") or 2),
            )
            if not proxies:
                return ok(
                    {
                        "hit": False,
                        "alias": alias,
                        "uniprot": uniprot,
                        "proxies": [],
                        "note": "no promoted cache entry — run Stage 1 multi-view retrieval",
                    }
                )
            return ok(
                {
                    "hit": True,
                    "alias": alias,
                    "uniprot": uniprot,
                    "proxies": proxies,
                    "n": len(proxies),
                    "note": "cache hit — skip Stage 1; predict with these proxy aliases",
                }
            )

        return dumps(await asyncio.to_thread(_run))


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "hit_lists": {
                "type": "array",
                "description": (
                    "List of per-modality RbpHit lists. Preferred shape: "
                    "[[{alias,score,...}, ...], [{...}, ...]]. "
                    "Also accepted: [{hits:[...]}, {hits:[...]}] (tool unwraps)."
                ),
                "items": {
                    "anyOf": [
                        {"type": "array"},
                        {
                            "type": "object",
                            "properties": {
                                "hits": {"type": "array"},
                            },
                        },
                    ]
                },
            },
            "hits": {
                "type": "array",
                "description": "Single flat RbpHit list (wrapped as one modality).",
            },
            "top_k": {"type": "integer", "default": 5},
            "exclude_aliases": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Aliases to exclude (usually the held/target RBP).",
            },
            "tau_drop": {
                "type": "number",
                "description": "Drop donors with fused score below this (default from config).",
            },
        },
        "required": [],
    }
)
class FuseSimilarityViewsTool(Tool):
    """Fuse multi-view hits with evolved (or default) fusion_weights."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "fuse_similarity_views"

    @property
    def description(self) -> str:
        return (
            "Fuse multi-view RbpHit lists into ranked donors using runtime "
            "fusion_weights. Prefer hit_lists=[hits_emb, hits_seq, struct, domain]. "
            "After fuse: call confidence_abstain(hits_emb) then predict_interaction "
            "on fused donor aliases (BUILD_SPEC order)."
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
        def _run():
            from app.core.runtime_config import (
                config_source,
                fusion_weights,
                tau_drop as cfg_tau,
            )
            from rbp_eval.fuse_hits import fuse_rbp_hits

            hit_lists = kwargs.get("hit_lists")
            if not hit_lists:
                # Dual-axis convenience: hits_emb + hits_seq (+ optional others)
                axes = []
                for key in (
                    "hits_emb",
                    "hits_seq",
                    "hits_struct",
                    "hits_dom",
                    "hits_rna",
                    "hits",
                ):
                    part = kwargs.get(key)
                    if isinstance(part, list) and part:
                        axes.append(part)
                if axes:
                    hit_lists = axes
                else:
                    return err(
                        "provide hit_lists, or hits_emb/hits_seq(/hits_struct/…), or hits"
                    )
            # LLM sometimes passes a modality dict at the top level
            if isinstance(hit_lists, dict):
                if "hits" in hit_lists and isinstance(hit_lists.get("hits"), list):
                    hit_lists = [hit_lists["hits"]]
                else:
                    hit_lists = list(hit_lists.values())
            if not isinstance(hit_lists, list):
                return err("hit_lists must be a list")
            lists: list[list] = []
            for item in hit_lists:
                if isinstance(item, list):
                    lists.append(item)
                elif isinstance(item, dict) and "hits" in item:
                    lists.append(list(item.get("hits") or []))
                elif isinstance(item, dict) and (
                    "alias" in item or "score" in item or "rbp_id" in item
                ):
                    # accidental flat list wrapped as one dict — skip noise
                    continue
            if not lists:
                return err(
                    "no hit lists to fuse; pass hit_lists as "
                    "[[{alias,score,...}], ...] or [{hits:[...]}, ...]"
                )
            excl = set(kwargs.get("exclude_aliases") or [])
            top_k = int(kwargs.get("top_k") or 5)
            tau = kwargs.get("tau_drop")
            tau_f = float(tau) if tau is not None else cfg_tau()
            weights = fusion_weights()
            donors = fuse_rbp_hits(
                lists,
                weights=weights,
                top_k=top_k,
                exclude_aliases=excl,
                use_rank_normalize=True,
                tau_drop=tau_f,
            )
            return ok(
                {
                    "donors": donors,
                    "hits": donors,
                    "n": len(donors),
                    "weights_source": config_source(),
                    "tau_drop": tau_f,
                    "fusion_weights": weights,
                    "next": "confidence_abstain on hits_emb, then predict_interaction",
                }
            )

        out = await asyncio.to_thread(_run)
        try:
            parsed = out if isinstance(out, dict) else None
            # dumps path below — mark fuse when status ok
        except Exception:
            parsed = None
        result = dumps(out)
        try:
            import json as _json

            obj = _json.loads(result) if isinstance(result, str) else None
            if isinstance(obj, dict) and obj.get("status") == "ok":
                from nanobot.agent.tools.rbp.turn_guards import mark_fuse_done

                mark_fuse_done()
        except Exception:
            pass
        return result
