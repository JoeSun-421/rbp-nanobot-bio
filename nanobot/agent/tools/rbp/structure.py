# -*- coding: utf-8 -*-
"""Proposal §5 P1/P2 — struct_similarity + predict_structure."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import dumps, err, get_delivery_client, ok, timed_call


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "pdb_path": {"type": "string"},
            "uniprot": {"type": "string", "description": "If no pdb_path, try structure_fetch"},
            "top_k": {"type": "integer", "default": 10},
            "refine_usalign": {"type": "boolean", "default": True},
        },
        "required": [],
    }
)
class StructSimilarityTool(Tool):
    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "struct_similarity"

    @property
    def description(self) -> str:
        return "Structural similarity via delivery foldseek (+ optional USalign refine)."

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        def _run():
            client = get_delivery_client()
            pdb = kwargs.get("pdb_path")
            if not pdb and kwargs.get("uniprot"):
                sf = client.call("structure_fetch", {"uniprot": kwargs["uniprot"]})
                pdb = sf.get("pdb_path")
                if not pdb:
                    raise RuntimeError(sf.get("error") or "structure_fetch failed")
            if not pdb:
                raise RuntimeError("pdb_path or uniprot required")
            st = client.call(
                "struct_similarity_foldseek",
                {"pdb_path": pdb, "top_k": int(kwargs.get("top_k") or 10)},
            )
            if st.get("error"):
                raise RuntimeError(st["error"])
            hits = list(st.get("hits") or [])
            if kwargs.get("refine_usalign", True) and hits:
                aliases = [h["alias"] for h in hits[:5] if h.get("alias")]
                usa = client.call(
                    "struct_align_usalign",
                    {"query_pdb": pdb, "targets": aliases},
                )
                if usa.get("hits"):
                    hits = usa["hits"]
            return {"hits": hits, "pdb_path": pdb}

        value, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        if error:
            return dumps(err(error, ms))
        return dumps(ok(value, ms))


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "sequence": {"type": "string"},
            "name": {"type": "string"},
            "uniprot_id": {"type": "string"},
        },
        "required": ["sequence"],
    }
)
class PredictStructureTool(Tool):
    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "predict_structure"

    @property
    def description(self) -> str:
        return "AF3 structure prediction fallback (delivery structure_predict_af3). GPU/slow."

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, sequence: str = "", name: str = "", **kwargs: Any) -> str:
        def _run():
            client = get_delivery_client(device="cuda")
            return client.call(
                "structure_predict_af3",
                {
                    "sequence": sequence,
                    "name": name or kwargs.get("uniprot_id") or "query",
                },
            )

        out, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        if error:
            return dumps(err(error, ms))
        if out.get("error") or out.get("ok") is False:
            return dumps(err(out.get("error") or "AF3 failed", ms))
        return dumps(
            ok(
                {
                    "structure": out.get("structure"),
                    "mean_plddt": out.get("mean_plddt"),
                    "ptm": out.get("ptm"),
                },
                ms,
            )
        )
