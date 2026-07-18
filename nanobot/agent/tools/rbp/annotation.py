# -*- coding: utf-8 -*-
"""Proposal §5 P1/P2 — get_func_annotation + literature_search."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import dumps, err, get_delivery_client, ok, timed_call


def reset_tool_turn_guards() -> None:
    """Clear per-turn anti-loop state (call at start of each chat / agent message)."""
    LiteratureSearchTool._calls_used = 0
    GetFuncAnnotationTool._cache.clear()
    GetFuncAnnotationTool._calls_used = 0
    try:
        from nanobot.agent.tools.rbp.predict import PredictInteractionTool

        PredictInteractionTool.reset_turn_guards()
    except Exception:
        pass


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "uniprot": {"type": "string"},
            "rbp_id": {"type": "string", "description": "Alias or UniProt; resolved first"},
            "offline": {
                "type": "boolean",
                "default": False,
                "description": "Ignored for caching; one fetch always tries UniProt then GO/Pfam.",
            },
        },
        "required": [],
    }
)
class GetFuncAnnotationTool(Tool):
    """P1 annotation — cached once per UniProt; hard cap on total calls (anti-loop)."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}
    _cache: dict[str, str] = {}
    _calls_used: int = 0
    _MAX_CALLS: int = 8  # target + ≤5 proxies + small headroom

    @property
    def name(self) -> str:
        return "get_func_annotation"

    @property
    def description(self) -> str:
        return (
            "Structured function JSON via delivery uniprot_annotation "
            "(falls back to go_pfam_lookup). Call once per UniProt; "
            "do not flip offline or re-query the same accession."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        raw = (kwargs.get("uniprot") or kwargs.get("rbp_id") or "").strip()
        if not raw:
            return dumps(err("uniprot or rbp_id required"))

        # Cache key ignores offline / rbp_id spelling variants after normalize.
        cache_key = raw.upper()
        cached = GetFuncAnnotationTool._cache.get(cache_key)
        if cached is not None:
            # Replay prior envelope so the model does not thrash on offline/online flips.
            return cached

        if GetFuncAnnotationTool._calls_used >= GetFuncAnnotationTool._MAX_CALLS:
            return dumps(
                err(
                    "get_func_annotation call budget exhausted this turn; "
                    "proceed to predict_interaction / verdict with available evidence"
                )
            )

        def _run():
            # Always try online UniProt first, then offline GO/Pfam — ignore offline flag.
            client = get_delivery_client(offline=False)
            up = raw
            res = client.call("resolve_rbp", {"query": up})
            if res.get("uniprot"):
                up = res["uniprot"]
            # After resolve, reuse any prior fetch for this accession.
            up_key = str(up).upper()
            hit = GetFuncAnnotationTool._cache.get(up_key)
            if hit is not None:
                return ("cached", up, hit)
            ann = client.call("uniprot_annotation", {"uniprot": up})
            if not ann.get("error") and not ann.get("skipped"):
                return ("fresh", up, ann.get("annotation") or ann)
            go = client.call("go_pfam_lookup", {"uniprot": up})
            if go.get("error"):
                raise RuntimeError(go["error"])
            return ("fresh", up, go)

        value, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        GetFuncAnnotationTool._calls_used += 1
        if error:
            out = dumps(err(error, ms))
            GetFuncAnnotationTool._cache[cache_key] = out
            return out

        kind, up, payload = value  # type: ignore[misc]
        if kind == "cached":
            GetFuncAnnotationTool._cache[cache_key] = payload
            return payload
        out = dumps(ok(payload, ms))
        GetFuncAnnotationTool._cache[cache_key] = out
        if isinstance(up, str) and up.upper() != cache_key:
            GetFuncAnnotationTool._cache[up.upper()] = out
        return out


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "rbp_name": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": [],
    }
)
class LiteratureSearchTool(Tool):
    """P2 literature — hard-capped to one successful call per turn (anti-loop)."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}
    _calls_used: int = 0
    _MAX_CALLS: int = 1

    @property
    def name(self) -> str:
        return "literature_search"

    @property
    def description(self) -> str:
        return (
            "Literature snippets via delivery literature_retrieval (network). "
            "At most ONE call per query; further calls return an error envelope."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        if LiteratureSearchTool._calls_used >= LiteratureSearchTool._MAX_CALLS:
            return dumps(
                err(
                    "literature_search already used once this session; "
                    "continue without more literature calls"
                )
            )
        name = kwargs.get("name") or kwargs.get("rbp_name") or ""
        if not name:
            return dumps(err("name or rbp_name required"))

        def _run():
            client = get_delivery_client(offline=False)
            return client.call(
                "literature_retrieval",
                {"name": name, "max_results": int(kwargs.get("max_results") or 5)},
            )

        out, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        LiteratureSearchTool._calls_used += 1
        if error:
            return dumps(err(error, ms))
        if out.get("error") or out.get("skipped"):
            return dumps(err(out.get("error") or out.get("reason") or "skipped", ms))
        return dumps(
            ok({"papers": out.get("papers") or out.get("results") or []}, ms)
        )
