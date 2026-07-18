# -*- coding: utf-8 -*-
"""Proposal §5 P0 — seq_similarity → delivery esm_similarity (+ optional mmseqs)."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import dumps, err, get_delivery_client, ok, timed_call


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "sequence": {"type": "string"},
            "target_sequence": {"type": "string"},
            "uniprot": {"type": "string"},
            "encoder": {"type": "string", "default": "esmc"},
            "device": {"type": "string", "default": "cpu"},
            "top_k": {"type": "integer", "default": 10},
            "also_mmseqs": {"type": "boolean", "default": False},
        },
        "required": [],
    }
)
class SeqSimilarityTool(Tool):
    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "seq_similarity"

    @property
    def description(self) -> str:
        return (
            "Sequence/embedding similarity vs catalogue. "
            "Default: delivery esm_similarity (ESM-C). Optional mmseqs via also_mmseqs."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        seq = kwargs.get("sequence") or kwargs.get("target_sequence") or ""
        if not seq:
            return dumps(err("sequence or target_sequence required"))

        def _run():
            client = get_delivery_client(device=kwargs.get("device") or "cpu")
            hits = []
            meta = {}
            esm = client.call(
                "esm_similarity",
                {
                    "sequence": seq,
                    "encoder": kwargs.get("encoder") or "esmc",
                    "device": kwargs.get("device") or "cpu",
                    "top_k": int(kwargs.get("top_k") or 10),
                    "uniprot": kwargs.get("uniprot"),
                },
            )
            meta["esm"] = {
                "error": esm.get("error"),
                "script": esm.get("_script"),
                "invocation": esm.get("_invocation"),
            }
            if esm.get("hits"):
                hits.extend(esm["hits"])
            if kwargs.get("also_mmseqs"):
                mm = client.call(
                    "protein_seq_similarity",
                    {"sequence": seq, "top_k": int(kwargs.get("top_k") or 10)},
                )
                meta["mmseqs"] = {"error": mm.get("error"), "script": mm.get("_script")}
                if mm.get("hits"):
                    hits.extend(mm["hits"])
            if not hits:
                raise RuntimeError(
                    meta.get("esm", {}).get("error")
                    or "no hits (need protein_embed conda on server)"
                )
            return {"hits": hits, "meta": meta}

        value, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        if error:
            return dumps(err(error, ms))
        return dumps(ok(value, ms))
