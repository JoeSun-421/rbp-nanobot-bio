# -*- coding: utf-8 -*-
"""Proposal / delivery-contract compliance tests (agent-side only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_tau_drop_filters_low_similarity():
    from rbp_eval.fuse_hits import fuse_rbp_hits

    hits = [
        [
            {"alias": "A", "score": 0.9, "metric": "esmc_cosine", "rank": 1},
            {"alias": "B", "score": 0.2, "metric": "esmc_cosine", "rank": 2},
            {"alias": "C", "score": 0.35, "metric": "esmc_cosine", "rank": 3},
        ]
    ]
    donors = fuse_rbp_hits(hits, top_k=5, tau_drop=0.30, use_rank_normalize=False)
    aliases = {d["alias"] for d in donors}
    assert "A" in aliases
    assert "B" not in aliases
    assert "C" in aliases
    assert len(donors) <= 5


def test_percent_identity_normalized_before_clamp():
    from rbp_eval.fuse_hits import fuse_rbp_hits

    donors = fuse_rbp_hits(
        [
            [
                {
                    "alias": "PTBP1",
                    "score": 97.0,
                    "metric": "seq_identity",
                    "rank": 1,
                }
            ]
        ],
        top_k=1,
        use_rank_normalize=False,
    )
    assert donors
    # 97% → 0.97, not clamped to 1.0 via raw>1 then min(1,97)
    assert abs(donors[0]["sim_by_modality"]["seq_identity"] - 0.97) < 1e-6


def test_fuse_proxy_candidates_respects_tau_and_ncand():
    from rbp_eval.fuse_hits import fuse_proxy_candidates

    fused = fuse_proxy_candidates(
        {
            "seq": [
                {"alias": "A", "score": 0.9},
                {"alias": "B", "score": 0.1},
            ],
            "struct": [{"alias": "A", "score": 0.8}],
            "func": [{"alias": "A", "score": 0.7}, {"alias": "C", "score": 0.95}],
        },
        n_cand=5,
        tau_drop=0.30,
    )
    ids = {p["rbp_id"] for p in fused}
    assert "A" in ids
    assert "B" not in ids
    assert "C" in ids
    assert len(fused) <= 5
    for p in fused:
        assert "similarity_score" in p
        assert "similarity_breakdown" in p
        assert "rationale" in p
        assert p["similarity_score"] >= 0.30


def test_label_thresholds_proposal():
    from app.core.verdict_schema import label_from_p_hat

    assert label_from_p_hat(0.80) == "Strong"
    assert label_from_p_hat(0.60) == "Likely"
    assert label_from_p_hat(0.30) == "Unlikely"
    assert label_from_p_hat(0.10) == "No"


def test_stage3_verdict_from_llm_json():
    """LLM touchpoints live in Nanobot+SKILL; verdict parse is still core."""
    from app.core.verdict_schema import extract_verdict_from_content

    content = json.dumps(
        {
            "label": "Likely",
            "p_hat": 0.85,
            "confidence": "medium",
            "explanation": "Proxy A is similar and predicts binding.",
            "supporting_rbps": [{"rbp_id": "P09651", "alias": "HNRNPA1", "prob": 0.9}],
        }
    )
    v = extract_verdict_from_content(content)
    assert v["label"] == "Likely"
    assert v["p_hat"] == 0.85
    assert "Proxy A" in v["explanation"]


def test_stage1_deterministic_fusion_in_rbp_eval():
    from rbp_eval.fuse_hits import fuse_proxy_candidates

    proxies = fuse_proxy_candidates(
        {
            "seq": [{"alias": "ELAVL1", "score": 0.9}],
            "func": [{"alias": "ELAVL1", "score": 0.8}],
        },
        n_cand=5,
        tau_drop=0.30,
    )
    assert proxies
    assert proxies[0]["rbp_id"] == "ELAVL1"
    assert proxies[0]["similarity_score"] >= 0.30


def test_defaults_match_proposal():
    import yaml

    cfg = yaml.safe_load((ROOT / "config" / "defaults.yaml").read_text(encoding="utf-8"))
    assert float(cfg["tau_drop"]) == 0.30
    assert int(cfg["n_cand"]) == 5
    assert float(cfg["near_match_seq_identity"]) == 0.95
    thr = cfg["label_thresholds"]
    assert thr["strong"] == 0.75
    assert thr["likely"] == 0.50
    assert thr["unlikely"] == 0.25
    assert cfg["llm"]["stage1_function_reasoning"] is True
    assert cfg["llm"]["stage3_explanation"] is True
    assert cfg["predict"]["aggregate"] == "weighted"
    assert cfg["axes"]["use_af3"] is True
    assert cfg["structure_policy"]["use_af3_fallback"] is True


def test_proposal_tool_names_registered():
    """P0–P2 tools come from nanobot.agent.tools.rbp (single source of truth)."""
    from app.backends.delivery.registry import STAGE_RAW_WHITELIST, build_proposal_tools

    tools = build_proposal_tools()
    names = {t.name for t in tools}
    for required in (
        "predict_interaction",
        "get_known_rbp_list",
        "seq_similarity",
        "struct_similarity",
        "get_func_annotation",
        "predict_structure",
        "literature_search",
        "lookup_proxy_cache",
        "fuse_similarity_views",
        "commit_proxy_candidates",
        "rna_similarity",
    ):
        assert required in names, f"missing curated tool {required}"
    # Tools are the rbp package classes, not a second wrapper stack
    assert any("nanobot.agent.tools.rbp" in type(t).__module__ for t in tools)
    assert "literature_retrieval" not in STAGE_RAW_WHITELIST
    assert "resolve_rbp" in STAGE_RAW_WHITELIST


def test_delivery_tree_untouched_marker():
    """Sanity: delivery package exists; science calls go through DeliveryToolClient."""
    delivery = ROOT.parent / "rhobind_agent_delivery"
    assert delivery.is_dir()
    client_src = (
        ROOT / "app" / "backends" / "delivery" / "client.py"
    ).read_text(encoding="utf-8")
    assert "DeliveryToolClient" in client_src


def test_near_match_threshold():
    from app.core.verdict_schema import is_near_match_score

    assert is_near_match_score(0.95) is True
    assert is_near_match_score(0.94) is False


def test_stage1_before_predict_in_skill_playbook():
    """Regression: SKILL playbook orders Stage 1 retrieval before Stage 2 predict."""
    skill = ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md"
    src = skill.read_text(encoding="utf-8")
    i_s0 = src.find("Stage 0")
    i_s1 = src.find("Stage 1")
    i_s2 = src.find("Stage 2")
    assert i_s0 > 0 and i_s1 > 0 and i_s2 > 0
    assert i_s0 < i_s1 < i_s2
    assert "Retrieve" in src[i_s1 : i_s1 + 120] or "retrieve" in src[i_s1 : i_s1 + 120].lower()
    assert "Predict" in src[i_s2 : i_s2 + 120] or "predict" in src[i_s2 : i_s2 + 80].lower()

def test_mvp_tool_whitelist_excludes_literature_raw():
    from nanobot.agent.tools.registry import ToolRegistry
    from nanobot.agent.tools.rbp.register import register_rbp_tools

    _reg, names = register_rbp_tools(ToolRegistry(), include_raw_delivery="whitelist")
    assert "literature_retrieval" not in names
    assert "resolve_rbp" in names
    assert "predict_interaction" in names
    # Curated P0–P2 + Stage 0/3 whitelist (count drifts with registry; keep bounded)
    assert 15 <= len(names) <= 40


def test_skill_playbook_locks_proposal_defaults_and_paths():
    """Proposal §4 / §8 + gate: SKILL must encode near-known, tau, N_cand, stages, caveats."""
    skill = ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md"
    src = skill.read_text(encoding="utf-8")
    assert "near-known" in src
    assert "0.30" in src or "0.3" in src
    assert "N_cand" in src or "n_cand" in src.lower()
    assert "Stage 3" in src
    assert "caveat" in src.lower()
    # Unseen path: retrieve before predict; own-head stops without transfer
    assert "in_panel=true" in src or "Own-head" in src or "own-head" in src
    assert "Stage 1" in src and "Stage 2" in src
    for key in ("label", "p_hat", "confidence", "explanation", "supporting_rbps"):
        assert key in src, f"verdict field {key} missing from SKILL"


def test_similarity_breakdown_in_fuse_and_verdict_supports_caveats():
    """Proposal §4 proxy object + IR caveats field."""
    from rbp_eval.fuse_hits import fuse_proxy_candidates
    from app.core.verdict_schema import normalize_verdict

    proxies = fuse_proxy_candidates(
        {"seq": [{"alias": "ELAVL1", "score": 0.9}]},
        n_cand=5,
        tau_drop=0.30,
    )
    assert proxies and "similarity_breakdown" in proxies[0]

    v = normalize_verdict(
        {
            "label": "Likely",
            "p_hat": 0.6,
            "confidence": 0.7,
            "explanation": "Grounded on tool scores only.",
            "supporting_rbps": [],
            "caveats": ["structure_axis unavailable"],
        }
    )
    assert v.get("caveats") == ["structure_axis unavailable"]
    assert isinstance(v.get("confidence"), (int, float, str))


def test_proposal_sot_tool_modules_exist_at_transition_path():
    """SoT is repo-root nanobot/agent/tools/rbp/ (nanobot-like overlay)."""
    sot = ROOT / "nanobot" / "agent" / "tools" / "rbp"
    for name in (
        "predict.py",
        "catalogue.py",
        "seq.py",
        "structure.py",
        "annotation.py",
        "common.py",
    ):
        assert (sot / name).is_file(), f"missing SoT module {name}"
    assert (ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md").is_file()


def test_proposal_documents_present():
    """Engineering guide §9 is the in-repo gate SoT; proposal PDFs are optional/external."""
    guide_path = ROOT / "docs" / "工程指南.zh.md"
    assert guide_path.is_file(), "docs/工程指南.zh.md must be tracked (gate SoT)"
    guide = guide_path.read_text(encoding="utf-8")
    assert "## 9. 改动门禁" in guide
    assert "Proposal" in guide or "提案" in guide
    assert (ROOT / "docs" / "proposal.md").is_file()
    assert (ROOT / "docs" / "proposal.zh.md").is_file()
    assert (ROOT / "docs" / "remediation-checklist.md").is_file()


def test_evolved_live_requires_decision_artifact_when_present():
    """If live evolved.yaml claims evolved:true, prefer an evolve-eval decision note when it exists."""
    import yaml

    evolved = ROOT / "config" / "evolved.yaml"
    if not evolved.is_file():
        return
    cfg = yaml.safe_load(evolved.read_text(encoding="utf-8")) or {}
    if not cfg.get("evolved"):
        return
    decision = ROOT / "artifacts" / "reports" / "evolve_eval_decision.md"
    if decision.is_file():
        text = decision.read_text(encoding="utf-8")
        assert "HOLD" in text or "PROMOTE" in text or "promote" in text.lower()
