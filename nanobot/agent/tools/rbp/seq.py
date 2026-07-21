# -*- coding: utf-8 -*-
"""P0 tool — seq_similarity → delivery esm_similarity (+ optional mmseqs)."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import (
    dumps,
    err,
    get_delivery_client,
    looks_like_rna,
    ok,
    resolve_device,
    resolve_protein_sequence,
    timed_call,
)


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "Protein AA sequence (≥20). Do NOT pass UniProt/alias here.",
            },
            "target_sequence": {
                "type": "string",
                "description": "Alias of sequence; UniProt/gene IDs are auto-resolved from catalogue.",
            },
            "uniprot": {
                "type": "string",
                "description": "Preferred: load AA seq from catalogue FASTA (e.g. O43251).",
            },
            "alias": {
                "type": "string",
                "description": "Preferred: gene symbol (e.g. RBFOX2) → catalogue FASTA.",
            },
            "query": {
                "type": "string",
                "description": "Alias or UniProt if sequence omitted.",
            },
            "encoder": {"type": "string", "default": "esmc"},
            "device": {
                "type": "string",
                "enum": ["auto", "cuda", "cpu"],
                "default": "auto",
                "description": "Prefer cuda when available (ESM-C / HANDOFF)",
            },
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
            "Sequence/embedding similarity vs catalogue (ESM-C). "
            "Pass alias=RBFOX2 or uniprot=O43251 (preferred). "
            "Protein AA sequences only; UniProt IDs are not valid `sequence` values; RNA is out of scope."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        raw = (kwargs.get("sequence") or kwargs.get("target_sequence") or "").strip()
        if raw and looks_like_rna(raw):
            return dumps(
                err(
                    "sequence looks like RNA; pass alias/uniprot for the protein, "
                    "or a real AA sequence"
                )
            )
        seq, src = resolve_protein_sequence(kwargs)
        if not seq:
            from nanobot.agent.tools.rbp.common import not_in_catalogue_hint

            ids = [
                str(kwargs.get(k))
                for k in ("alias", "uniprot", "query", "rbp_id")
                if kwargs.get(k)
            ]
            return dumps(
                err(
                    not_in_catalogue_hint(*ids)
                    + " Or pass protein AA `sequence` ≥20 explicitly."
                )
            )

        def _run():
            device = resolve_device(kwargs.get("device"))
            client = get_delivery_client(device=device)
            hits = []
            meta: dict[str, Any] = {"sequence_source": src, "seq_len": len(seq)}
            also_mmseqs = bool(kwargs.get("also_mmseqs"))
            esm = client.call(
                "esm_similarity",
                {
                    "sequence": seq,
                    "encoder": kwargs.get("encoder") or "esmc",
                    "device": device,
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
            # Auto-fallback to mmseqs when ESM fails (or explicitly requested)
            if (not hits and esm.get("error")) or also_mmseqs:
                mm = client.call(
                    "protein_seq_similarity",
                    {"sequence": seq, "top_k": int(kwargs.get("top_k") or 10)},
                )
                meta["mmseqs"] = {"error": mm.get("error"), "script": mm.get("_script")}
                if mm.get("hits"):
                    hits.extend(mm["hits"])
                    meta["fallback"] = "mmseqs"
                    meta["confidence_hint"] = "low"
            if not hits:
                raise RuntimeError(
                    (meta.get("esm", {}) or {}).get("error")
                    or (meta.get("mmseqs", {}) or {}).get("error")
                    or "no hits (need protein_embed conda / HF weights; do not invent similarity)"
                )
            return {"hits": hits, "meta": meta}

        value, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        if error:
            return dumps(err(error, ms))
        return dumps(ok(value, ms))
