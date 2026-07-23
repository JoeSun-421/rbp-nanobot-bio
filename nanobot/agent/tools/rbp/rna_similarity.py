# -*- coding: utf-8 -*-
"""Agent-local RNA similarity (RNA-FM bridge / mock bank)."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import dumps, err, ok


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "rna": {
                "type": "string",
                "description": "Query RNA sequence (A/C/G/U/T). Required.",
            },
            "sequence": {
                "type": "string",
                "description": "Alias of rna.",
            },
            "top_k": {"type": "integer", "default": 5},
            "exclude_aliases": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Aliases to exclude (usually the target RBP).",
            },
            "window": {
                "type": "integer",
                "default": 128,
                "description": "Window length aligned with RhoBind tiling (nt).",
            },
        },
        "required": [],
    }
)
class RnaSimilarityTool(Tool):
    """RNA-FM-style embedding similarity vs a local catalogue RNA bank."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "rna_similarity"

    @property
    def description(self) -> str:
        return (
            "RNA embedding similarity vs a local bank of catalogue-associated "
            "RNA windows (RNA-FM bridge; mock k-mer embedder when no checkpoint). "
            "Call in Stage 1 when query RNA is present, in parallel with "
            "seq_similarity. On failure, continue and note rna_axis=unavailable."
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
            rna = (kwargs.get("rna") or kwargs.get("sequence") or "").strip()
            if not rna:
                return err("provide rna (query RNA sequence)")
            # Cheap RNA check: mostly ACGTU
            letters = sum(1 for c in rna.upper() if c in "ACGTU")
            if letters < max(8, int(0.7 * len(rna))):
                return err("rna looks non-nucleic; pass an RNA sequence, not protein")
            try:
                from nanobot.agent.tools.rbp.common import rna_similarity_hits_facade

                excl = set(kwargs.get("exclude_aliases") or [])
                top_k = int(kwargs.get("top_k") or 5)
                window = int(kwargs.get("window") or 128)
                out = rna_similarity_hits_facade(
                    rna,
                    top_k=top_k,
                    exclude_aliases=excl,
                    window=window,
                )
                if not out.get("hits"):
                    return ok(
                        {
                            **out,
                            "rna_axis": "unavailable",
                            "note": "no bank hits — continue Stage 1 without RNA view",
                        }
                    )
                return ok({**out, "rna_axis": "ok"})
            except Exception as e:
                return ok(
                    {
                        "hits": [],
                        "n": 0,
                        "rna_axis": "unavailable",
                        "metric": "rna_embed",
                        "note": f"rna_similarity failed: {type(e).__name__}: {e}",
                    }
                )

        return dumps(await asyncio.to_thread(_run))
