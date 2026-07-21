# -*- coding: utf-8 -*-
"""Offline unit tests for agent-local rna_similarity (mock embedder)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_rna_fm_mock_hits_deterministic(tmp_path):
    from rbp_agent.backends.rna_fm.client import (
        ensure_default_bank,
        rna_similarity_hits,
    )

    bank = tmp_path / "bank.json"
    ensure_default_bank(bank)
    rna = "CUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCU"
    a = rna_similarity_hits(rna, top_k=3, bank_path=bank, mode="mock")
    b = rna_similarity_hits(rna, top_k=3, bank_path=bank, mode="mock")
    assert a["backend"] == "mock"
    assert a["hits"]
    assert a["hits"][0]["metric"] == "rna_embed"
    assert a["hits"] == b["hits"]
    # CU-rich window should prefer PTBP1 fixture
    assert a["hits"][0]["alias"] == "PTBP1"


def test_rna_similarity_tool_registers_and_runs(tmp_path, monkeypatch):
    from rbp_agent.backends.rna_fm import client as rna_client
    from nanobot.agent.tools.rbp.rna_similarity import RnaSimilarityTool
    from nanobot.agent.tools.rbp import ALL_RBP_TOOL_CLASSES
    from rbp_agent.backends.delivery.registry import PROPOSAL_TOOL_NAMES, build_proposal_tools
    from rbp_agent.backends.delivery.stage_tools import STAGE_TOOL_SETS

    bank = tmp_path / "bank.json"
    rna_client.ensure_default_bank(bank)
    monkeypatch.setenv("RNA_BANK_PATH", str(bank))
    monkeypatch.setenv("RNA_FM_MODE", "mock")

    assert "rna_similarity" in PROPOSAL_TOOL_NAMES
    assert "rna_similarity" in STAGE_TOOL_SETS["stage1"]
    assert any(c.__name__ == "RnaSimilarityTool" for c in ALL_RBP_TOOL_CLASSES)
    names = {t.name for t in build_proposal_tools()}
    assert "rna_similarity" in names

    tool = RnaSimilarityTool()
    rna = "AUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUU"
    out = asyncio.run(tool.execute(rna=rna, top_k=3))
    data = json.loads(out)
    assert data["status"] == "ok"
    assert data["value"]["rna_axis"] == "ok"
    assert data["value"]["hits"]
    assert data["value"]["hits"][0]["metric"] == "rna_embed"


def test_mapping_includes_rna_similarity():
    mapping = yaml.safe_load(
        (ROOT / "rbp_agent" / "backends" / "delivery" / "mapping.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert mapping["rna_similarity"]["type"] == "agent_local"


def test_fuse_accepts_rna_embed_weight():
    from rbp_eval.fuse_hits import fuse_rbp_hits

    hits = [
        [
            {"alias": "PTBP1", "score": 0.9, "metric": "rna_embed"},
            {"alias": "QKI", "score": 0.5, "metric": "rna_embed"},
        ],
        [
            {"alias": "PTBP1", "score": 0.8, "metric": "esmc_cosine"},
        ],
    ]
    donors = fuse_rbp_hits(hits, top_k=2, weights={"rna_embed": 0.3, "esmc_cosine": 1.0})
    assert donors
    assert donors[0]["alias"] == "PTBP1"
    assert "rna_embed" in (donors[0].get("sim_by_modality") or {})


def test_assign_strata_tags():
    from rbp_eval.evaluation_plan import assign_strata, STRATA_TAGS

    assert "own_head" in assign_strata(in_panel=True, mode="own_head")
    assert "in_panel_transfer" in assign_strata(in_panel=False, mode="transfer")
    assert "dark_protein" in assign_strata(prior_missing=True, dark=True)
    assert "cross_kingdom" in assign_strata(kingdom="bacteria")
    assert set(STRATA_TAGS) >= {"own_head", "dark_protein", "cross_kingdom"}
