# -*- coding: utf-8 -*-
"""Proposal §4 fidelity: commit_proxy_candidates + weighted aggregation."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_proposal_breakdown_maps_metrics():
    from rbp_eval.fuse_hits import proposal_breakdown

    br = proposal_breakdown(
        {"esmc_cosine": 0.9, "tm_score": 0.7, "domain_jaccard": 0.5, "noise": 0.1}
    )
    assert br["seq"] == 0.9
    assert br["struct"] == 0.7
    assert br["func"] == 0.5


def test_aggregate_probability_weighted_mean():
    from rbp_eval.fuse_hits import aggregate_probability

    out = aggregate_probability(
        [
            {"rbp_id": "A", "similarity_score": 1.0},
            {"rbp_id": "B", "similarity_score": 0.5},
        ],
        [
            {"alias": "A", "prob": 0.8, "confidence": 1.0},
            {"alias": "B", "prob": 0.2, "confidence": 1.0},
        ],
    )
    # (1.0*0.8 + 0.5*0.2) / (1.0+0.5) = 0.9/1.5 = 0.6
    assert abs(out["p_hat"] - 0.6) < 1e-6
    assert len(out["terms"]) == 2


def test_aggregate_probability_defaults_c_to_one():
    from rbp_eval.fuse_hits import aggregate_probability

    out = aggregate_probability(
        [{"rbp_id": "A", "similarity_score": 1.0}],
        [{"alias": "A", "prob": 0.4}],  # no confidence
    )
    assert abs(out["p_hat"] - 0.4) < 1e-6
    assert out["terms"][0]["c"] == 1.0


def test_commit_proxy_candidates_and_gate():
    import importlib.util

    path = ROOT / "nanobot" / "agent" / "tools" / "rbp" / "turn_guards.py"
    spec = importlib.util.spec_from_file_location("tg_commit", path)
    assert spec and spec.loader
    tg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tg)

    tg.reset_stage_guards()
    assert tg.commit_blocked_reason() and "fuse" in tg.commit_blocked_reason().lower()
    tg.mark_fuse_done()
    assert tg.commit_blocked_reason() is None

    tg.set_committed_proxies(
        [
            {
                "rbp_id": "PTBP1",
                "alias": "PTBP1",
                "similarity_score": 0.8,
                "similarity_breakdown": {"seq": 0.9},
                "rationale": "test",
            }
        ]
    )
    assert tg.commit_done()
    assert tg.committed_proxies()[0]["similarity_score"] == 0.8


def test_commit_tool_filters_tau_and_persists():
    from nanobot.agent.tools.rbp.commit_proxies import CommitProxyCandidatesTool
    from nanobot.agent.tools.rbp.turn_guards import (
        committed_proxies,
        mark_fuse_done,
        reset_stage_guards,
    )

    reset_stage_guards()
    mark_fuse_done()
    tool = CommitProxyCandidatesTool()
    raw = asyncio.run(
        tool.execute(
            candidates=[
                {
                    "rbp_id": "A",
                    "similarity_score": 0.9,
                    "similarity_breakdown": {"seq": 0.9, "struct": 0.5, "func": 0.7},
                    "rationale": "high",
                },
                {
                    "rbp_id": "B",
                    "similarity_score": 0.1,
                    "similarity_breakdown": {"seq": 0.1},
                    "rationale": "low",
                },
            ],
            tau_drop=0.30,
            n_cand=5,
        )
    )
    obj = json.loads(raw)
    assert obj["status"] == "ok"
    assert obj["value"]["n"] == 1
    assert committed_proxies()[0]["rbp_id"] == "A"


def test_defaults_section4_weighted_and_af3():
    import yaml

    cfg = yaml.safe_load((ROOT / "config" / "defaults.yaml").read_text(encoding="utf-8"))
    assert cfg["predict"]["aggregate"] == "weighted"
    assert cfg["axes"]["use_af3"] is True
    assert cfg["structure_policy"]["use_af3_fallback"] is True


def test_commit_proxy_tool_registered():
    from app.backends.delivery.registry import build_proposal_tools

    names = {t.name for t in build_proposal_tools()}
    assert "commit_proxy_candidates" in names
