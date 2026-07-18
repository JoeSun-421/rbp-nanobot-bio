# -*- coding: utf-8 -*-
"""Layout + import smoke (agent path, not pipeline MVP)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_layout_proposal_paths():
    assert (ROOT / "nanobot" / "agent" / "tools" / "rbp" / "predict.py").is_file()
    assert (ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md").is_file()
    assert (ROOT / "backends" / "delivery" / "client.py").is_file()
    assert (ROOT / "rbp_eval" / "runner.py").is_file()
    assert (ROOT / "integrate.py").is_file()
    assert (ROOT / "cli.py").is_file()
    # Removed shims / non-proposal product dirs / fixed pipeline
    assert not (ROOT / "rbp_tools").exists()
    assert not (ROOT / "demos").exists()
    assert not (ROOT / "out").exists()
    assert not (ROOT / "core" / "pipeline.py").exists()
    assert not (ROOT / "core" / "llm_touchpoints.py").exists()
    # Product core surface
    assert (ROOT / "core" / "verdict_schema.py").is_file()
    assert (ROOT / "core" / "onboard.py").is_file()
    assert (ROOT / "core" / "chat_ux.py").is_file()


def test_verdict_schema():
    from core.verdict_schema import normalize_verdict, validate_verdict

    v = normalize_verdict(
        {
            "label": "Likely",
            "p_hat": 0.6,
            "confidence": "medium",
            "explanation": "ok",
            "supporting_rbps": [],
        }
    )
    ok, errs = validate_verdict(v)
    assert ok, errs


def test_fuse_and_label():
    from core.verdict_schema import label_from_p_hat
    from rbp_eval.fusion import fuse_proxy_candidates
    from rbp_eval.fuse_hits import fuse_rbp_hits

    fused = fuse_proxy_candidates(
        {
            "seq": [{"alias": "A", "score": 0.9}],
            "struct": [{"alias": "A", "score": 0.5}],
        },
        n_cand=5,
        tau_drop=0.1,
    )
    assert fused
    assert label_from_p_hat(0.8) in ("Strong", "Likely", "Unlikely", "No")
    donors = fuse_rbp_hits(
        [[{"alias": "ELAVL1", "score": 0.9, "metric": "domain_overlap", "rank": 1}]],
        top_k=3,
    )
    assert isinstance(donors, list)


def test_agent_default_no_fallback():
    from integrate import RBPAgent

    # Instantiation may fail without delivery; only check default flag via signature
    import inspect

    sig = inspect.signature(RBPAgent.__init__)
    assert sig.parameters["allow_fallback"].default is False


def test_delivery_resolve():
    from backends.delivery.client import DeliveryToolClient
    from backends.delivery.env import apply_delivery_env

    apply_delivery_env()
    cli = DeliveryToolClient(offline=True, device="cpu", use_conda=False)
    r = cli.call("resolve_rbp", {"query": "PTBP1"})
    assert r.get("matched")
    assert r.get("alias") == "PTBP1"
