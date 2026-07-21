# -*- coding: utf-8 -*-
"""Self-evolution smoke tests (agent-side only; no delivery edits)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_config_loads():
    from rbp_agent.core.runtime_config import (
        abstain_thresholds,
        clear_runtime_config_cache,
        fusion_weights,
        label_thresholds,
        load_runtime_config,
    )

    clear_runtime_config_cache()
    cfg = load_runtime_config()
    assert isinstance(cfg, dict)
    w = fusion_weights()
    assert "esmc_cosine" in w
    thr = label_thresholds()
    assert thr["strong"] >= thr["likely"] >= thr["unlikely"]
    ab = abstain_thresholds()
    assert ab["esmc_cosine"] > 0
    assert "fused" in ab


def test_confidence_abstain_injects_evolved_thresholds():
    from rbp_agent.backends.delivery.registry import _normalize_delivery_payload
    from rbp_agent.core.runtime_config import abstain_thresholds, clear_runtime_config_cache

    clear_runtime_config_cache()
    expected = abstain_thresholds()
    out = _normalize_delivery_payload(
        "confidence_abstain",
        {"hits": [{"alias": "PTBP1", "score": 0.9, "metric": "esmc_cosine"}]},
    )
    assert out["thresholds"]["esmc_cosine"] == expected["esmc_cosine"]
    # explicit override wins
    out2 = _normalize_delivery_payload(
        "confidence_abstain",
        {
            "hits": [{"alias": "PTBP1", "score": 0.9}],
            "thresholds": {"esmc_cosine": 0.99},
        },
    )
    assert out2["thresholds"]["esmc_cosine"] == 0.99
    assert out2["thresholds"]["fused"] == expected["fused"]


def test_fuse_similarity_views_tool():
    from nanobot.agent.tools.rbp.evolve_tools import FuseSimilarityViewsTool
    import asyncio

    tool = FuseSimilarityViewsTool()
    hits_a = [
        {"alias": "U2AF2", "uniprot": "P26368", "score": 0.9, "metric": "esmc_cosine"},
        {"alias": "QKI", "uniprot": "Q96PU8", "score": 0.8, "metric": "esmc_cosine"},
    ]
    hits_b = [
        {"alias": "U2AF2", "uniprot": "P26368", "score": 1.0, "metric": "domain_overlap"},
    ]
    out = asyncio.run(
        tool.execute(hit_lists=[hits_a, hits_b], top_k=3, exclude_aliases=["PTBP1"])
    )
    data = json.loads(out)
    assert data["status"] == "ok"
    donors = data["value"]["donors"]
    assert donors
    assert donors[0]["alias"] == "U2AF2"


def test_lookup_proxy_cache_tool_miss(tmp_path, monkeypatch):
    from rbp_eval import proxy_cache as pc
    import asyncio
    from nanobot.agent.tools.rbp.evolve_tools import LookupProxyCacheTool

    cache_path = tmp_path / "proxy_map.json"
    cache_path.write_text(
        json.dumps({"version": 1, "entries": {}, "stats": {}}), encoding="utf-8"
    )
    monkeypatch.setattr(pc, "DEFAULT_CACHE", cache_path)
    tool = LookupProxyCacheTool()
    out = asyncio.run(tool.execute(alias="NSUN2"))
    data = json.loads(out)
    assert data["status"] == "ok"
    assert data["value"]["hit"] is False


def test_lookup_proxy_cache_tool_hit(tmp_path, monkeypatch):
    from rbp_eval import proxy_cache as pc
    import asyncio
    from nanobot.agent.tools.rbp.evolve_tools import LookupProxyCacheTool

    cache_path = tmp_path / "proxy_map.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    "alias:NSUN2": {
                        "alias": "NSUN2",
                        "hits": 5,
                        "promoted": True,
                        "proxies": [{"alias": "NOP2"}, {"alias": "NSUN5"}],
                    }
                },
                "stats": {"n_entries": 1, "n_promoted": 1},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pc, "DEFAULT_CACHE", cache_path)
    tool = LookupProxyCacheTool()
    out = asyncio.run(tool.execute(alias="NSUN2"))
    data = json.loads(out)
    assert data["value"]["hit"] is True
    assert data["value"]["proxies"][0]["alias"] == "NOP2"


def test_retune_label_thresholds_ce():
    from rbp_eval.evaluator import retune_label_thresholds

    labels = [{"p_hat": 0.9, "y": 1} for _ in range(4)] + [
        {"p_hat": 0.1, "y": 0} for _ in range(4)
    ]
    out = retune_label_thresholds(labels)
    assert out["status"] == "ok"
    assert out["objective"] == "calibrated_cross_entropy"
    assert out["thresholds"]["likely"] > 0.2


def test_tool_attribution_supporting_mass():
    from rbp_eval.evaluator import tool_attribution

    results = [
        {
            "mode": "transfer",
            "retrieval": {"domain": {"ok": True}, "esm_similarity": {"ok": True}},
            "evidence_table": [
                {
                    "alias": "U2AF2",
                    "sim_by_modality": {"esmc_cosine": 0.9, "domain_overlap": 0.8},
                }
            ],
            "verdict": {
                "p_hat": 0.7,
                "supporting_rbps": [
                    {"alias": "U2AF2", "similarity_score": 0.9, "prob": 0.7}
                ],
            },
        }
    ]
    attr = tool_attribution(results)
    assert attr["n_success"] == 1
    assert attr["supporting_evidence_fraction"] or attr["modality_mass"]


def test_rbp_trace_hook_query_end(tmp_path):
    import asyncio
    from rbp_eval.nanobot_hooks import RBPTraceHook

    path = tmp_path / "t.jsonl"
    hook = RBPTraceHook(path, session_key="test")
    hook.note_query(alias="NSUN2")
    hook._last_donors = [{"alias": "NOP2", "score": 0.8}]
    content = json.dumps(
        {
            "label": "Likely",
            "p_hat": 0.6,
            "confidence": "medium",
            "explanation": "test",
            "supporting_rbps": [{"alias": "NOP2", "prob": 0.6, "similarity_score": 0.8}],
        }
    )
    hook.emit_query_end(content=content, tools_used=["resolve_rbp", "lookup_proxy_cache"])
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    assert any(r.get("type") == "query_end" for r in rows)
    qe = next(r for r in rows if r["type"] == "query_end")
    assert qe["verdict"]["p_hat"] == 0.6
    assert qe["donors"]


def test_run_self_evolution_offline(tmp_path, monkeypatch):
    from rbp_eval import evaluator as ev
    from rbp_eval.evaluator import run_self_evolution

    # redirect report/config writes
    report_path = tmp_path / "self_evolution_report.json"
    cfg_path = tmp_path / "evolved.yaml"
    cand_path = tmp_path / "evolved.candidate.yaml"
    monkeypatch.setattr(ev, "EVOLVED_REPORT", report_path)
    monkeypatch.setattr(ev, "EVOLVED_CONFIG", cfg_path)
    monkeypatch.setattr(ev, "CANDIDATE_CONFIG", cand_path)

    results = [
        {
            "query": {"alias": "PTBP1"},
            "mode": "retrieval_only",
            "donors": [
                {"alias": "U2AF2", "score": 0.9, "metric": "domain_overlap"},
                {"alias": "ELAVL1", "score": 0.7, "metric": "domain_overlap"},
            ],
            "retrieval": {"domain": {"ok": True, "n": 2}},
            "evidence_table": [
                {"alias": "U2AF2", "score": 0.9, "sim_by_modality": {"domain_overlap": 0.9}},
            ],
            "verdict": {
                "label": "No",
                "p_hat": None,
                "confidence": "low",
                "explanation": "stub",
                "supporting_rbps": [{"alias": "U2AF2", "similarity_score": 0.9}],
            },
        }
    ]
    held = {
        "PTBP1": [
            [
                {"alias": "U2AF2", "score": 0.9, "metric": "domain_overlap"},
                {"alias": "ELAVL1", "score": 0.7, "metric": "domain_overlap"},
            ]
        ]
    }
    # weight retune needs LOO matrix; if missing, status may still be ok with 0 score
    report = run_self_evolution(
        results,
        held_to_hit_lists=held,
        traces=[
            {
                "type": "query_end",
                "alias": "NSUN2",
                "donors": [{"alias": "NOP2"}, {"alias": "NSUN5"}],
                "verdict": {},
            },
            {
                "type": "query_end",
                "alias": "NSUN2",
                "donors": [{"alias": "NOP2"}, {"alias": "NSUN5"}],
                "verdict": {},
            },
        ],
        write_config=True,
    )
    assert report_path.is_file()
    d = report.to_dict()
    assert "tool_attribution" in d
    assert "toolkit_proposals" in d


def test_retune_abstain_thresholds_grid():
    from rbp_eval.evaluator import retune_abstain_thresholds

    held = {
        "PTBP1": [
            [
                {"alias": "U2AF2", "score": 0.9, "metric": "domain_overlap"},
                {"alias": "ELAVL1", "score": 0.4, "metric": "domain_overlap"},
            ]
        ],
        "QKI": [
            [
                {"alias": "HNRNPC", "score": 0.2, "metric": "esmc_cosine"},
            ]
        ],
    }
    out = retune_abstain_thresholds(held, top_k=3, grid=[0.2, 0.45, 0.7])
    assert out["status"] == "ok"
    assert "tuned_thresholds" in out
    assert "fused" in out["tuned_thresholds"]
    assert "history" in out


def test_run_self_evolution_includes_abstain_retune(tmp_path, monkeypatch):
    from rbp_eval import evaluator as ev
    from rbp_eval.evaluator import run_self_evolution

    report_path = tmp_path / "self_evolution_report.json"
    cfg_path = tmp_path / "evolved.yaml"
    cand_path = tmp_path / "evolved.candidate.yaml"
    monkeypatch.setattr(ev, "EVOLVED_REPORT", report_path)
    monkeypatch.setattr(ev, "EVOLVED_CONFIG", cfg_path)
    monkeypatch.setattr(ev, "CANDIDATE_CONFIG", cand_path)

    results = [
        {
            "query": {"alias": "PTBP1"},
            "mode": "retrieval_only",
            "donors": [{"alias": "U2AF2", "score": 0.9, "metric": "domain_overlap"}],
            "retrieval": {"domain": {"ok": True, "n": 1}},
            "evidence_table": [
                {"alias": "U2AF2", "score": 0.9, "sim_by_modality": {"domain_overlap": 0.9}},
            ],
            "verdict": {
                "label": "No",
                "p_hat": None,
                "confidence": "low",
                "explanation": "stub",
                "supporting_rbps": [{"alias": "U2AF2", "similarity_score": 0.9}],
            },
        }
    ]
    held = {
        "PTBP1": [
            [{"alias": "U2AF2", "score": 0.9, "metric": "domain_overlap"}]
        ]
    }
    report = run_self_evolution(
        results, held_to_hit_lists=held, write_config=True
    )
    d = report.to_dict()
    assert "abstain_retune" in d
    assert d["abstain_retune"].get("status") in ("ok", "skipped")
    if d["abstain_retune"].get("status") == "ok":
        assert cand_path.is_file()
        text = cand_path.read_text(encoding="utf-8")
        assert "abstain_thresholds" in text


def test_proposal_tools_include_evolve():
    from rbp_agent.backends.delivery.registry import PROPOSAL_TOOL_NAMES, build_proposal_tools

    assert "lookup_proxy_cache" in PROPOSAL_TOOL_NAMES
    assert "fuse_similarity_views" in PROPOSAL_TOOL_NAMES
    assert "rna_similarity" in PROPOSAL_TOOL_NAMES
    names = {t.name for t in build_proposal_tools()}
    assert "lookup_proxy_cache" in names
    assert "fuse_similarity_views" in names
    assert "rna_similarity" in names
