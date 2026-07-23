# -*- coding: utf-8 -*-
"""Unit tests for Stage 0–3 turn guards (BUILD_SPEC fuse → abstain → predict)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_transfer_predict_requires_fuse_then_abstain(monkeypatch):
    # Load SoT module directly (overlay may not be synced yet).
    import importlib.util

    path = ROOT / "nanobot" / "agent" / "tools" / "rbp" / "turn_guards.py"
    spec = importlib.util.spec_from_file_location("turn_guards_sot", path)
    assert spec and spec.loader
    tg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tg)

    tg.reset_stage_guards()
    monkeypatch.setattr(tg, "alias_has_panel_head", lambda *a, **k: False)

    reason = tg.transfer_predict_blocked_reason(
        force_transfer=True, rbps=["FUS"], cohort="K562"
    )
    assert reason and "fuse_similarity_views" in reason

    tg.mark_fuse_done()
    reason = tg.transfer_predict_blocked_reason(
        force_transfer=True, rbps=["FUS"], cohort="K562"
    )
    assert reason and "confidence_abstain" in reason

    tg.mark_abstain_done()
    assert (
        tg.transfer_predict_blocked_reason(
            force_transfer=True, rbps=["FUS"], cohort="K562"
        )
        is None
    )


def test_abstain_requires_fuse_first():
    import importlib.util

    path = ROOT / "nanobot" / "agent" / "tools" / "rbp" / "turn_guards.py"
    spec = importlib.util.spec_from_file_location("turn_guards_sot2", path)
    assert spec and spec.loader
    tg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tg)

    tg.reset_stage_guards()
    reason = tg.abstain_blocked_reason()
    assert reason and "fuse_similarity_views" in reason
    tg.mark_fuse_done()
    assert tg.abstain_blocked_reason() is None


def test_own_head_single_alias_skips_abstain_gate(monkeypatch):
    import importlib.util

    path = ROOT / "nanobot" / "agent" / "tools" / "rbp" / "turn_guards.py"
    spec = importlib.util.spec_from_file_location("turn_guards_sot3", path)
    assert spec and spec.loader
    tg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tg)

    tg.reset_stage_guards()
    monkeypatch.setattr(tg, "alias_has_panel_head", lambda *a, **k: True)
    assert (
        tg.transfer_predict_blocked_reason(
            force_transfer=False, rbps=["PTBP1"], cohort="K562"
        )
        is None
    )
