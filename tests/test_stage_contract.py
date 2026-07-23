# -*- coding: utf-8 -*-
"""Stage contract compliance (A3 concurrency_safe + B2 dependency edges).

Verifies:
* Stage-1 retrieve curated tools are ``concurrency_safe`` so the nanobot runner
  can batch them into a single ``asyncio.gather`` (true parallel four-view retrieval).
* ``stage_contract.REQUIRES`` is acyclic and contains the fuse → abstain → predict
  serial edges the turn guards enforce.
* ``turn_guards`` consults the contract (data-driven, not hardcoded duplicates).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_sot(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_stage_retrieve_curated_tools_are_concurrency_safe():
    from nanobot.agent.tools.rbp import ALL_RBP_TOOL_CLASSES
    from nanobot.agent.tools.rbp.stage_contract import STAGE_RETRIEVE

    curated_names = {cls().name for cls in ALL_RBP_TOOL_CLASSES}
    retrieve_curated = curated_names & STAGE_RETRIEVE
    assert retrieve_curated, "expected curated retrieve tools in STAGE_RETRIEVE"
    for cls in ALL_RBP_TOOL_CLASSES:
        tool = cls()
        if tool.name in STAGE_RETRIEVE:
            assert tool.concurrency_safe, (
                f"{tool.name} must be concurrency_safe for Stage-1 parallel batching"
            )


def test_requires_is_acyclic_and_has_serial_edges():
    from nanobot.agent.tools.rbp.stage_contract import REQUIRES, is_acyclic

    assert is_acyclic(), "REQUIRES edges must not form a cycle"
    # fuse → (any retrieve); abstain → fuse; predict → abstain (transfer path)
    assert "__any_retrieve__" in REQUIRES["fuse_similarity_views"]
    assert "fuse_similarity_views" in REQUIRES["confidence_abstain"]
    assert "confidence_abstain" in REQUIRES["predict_interaction"]


def test_turn_guards_consults_contract():
    sc = _load_sot("stage_contract_sot", "nanobot/agent/tools/rbp/stage_contract.py")
    tg = _load_sot("turn_guards_sot4", "nanobot/agent/tools/rbp/turn_guards.py")

    # RETRIEVE_AFTER_OWN_HEAD should be sourced from stage_contract, not hardcoded.
    assert tg.RETRIEVE_AFTER_OWN_HEAD == sc.OWN_HEAD_STOP_BLOCKED
    # The serial edges the guards enforce are exactly those declared in the contract.
    assert "confidence_abstain" in sc.REQUIRES["predict_interaction"]
    assert "fuse_similarity_views" in sc.REQUIRES["confidence_abstain"]


def test_fuse_blocked_reason_available_and_uses_contract():
    tg = _load_sot("turn_guards_sot5", "nanobot/agent/tools/rbp/turn_guards.py")
    tg.reset_stage_guards()
    # No retrieve done → fuse would be blocked (soft guard, not wired by default).
    assert tg.fuse_blocked_reason() is not None
    tg.mark_retrieve_done("seq_similarity")
    assert tg.fuse_blocked_reason() is None
