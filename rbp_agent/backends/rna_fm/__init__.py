# -*- coding: utf-8 -*-
"""RNA-FM-style embedding bridge (agent-local; delivery untouched)."""

from rbp_agent.backends.rna_fm.client import (
    RnaFmClient,
    rna_similarity_hits,
)

__all__ = ["RnaFmClient", "rna_similarity_hits"]
