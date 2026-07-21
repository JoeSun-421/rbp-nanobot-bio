# -*- coding: utf-8 -*-
"""Stage-0 own-head contract (delivery BUILD_SPEC §4 / examples)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_skill_always_on_and_own_head_playbook(tmp_path):
    from rbp_agent.integrate import ensure_workspace_skill
    from nanobot.agent.skills import SkillsLoader

    skill = ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "always: true" in text
    assert "in_panel" in text
    assert "own-head" in text.lower() or "OWN HEAD" in text
    assert "STOP" in text

    ensure_workspace_skill(tmp_path)
    loader = SkillsLoader(tmp_path, builtin_skills_dir=ROOT / "nanobot" / "skills")
    always = loader.get_always_skills()
    assert "rbp-agent" in always


def test_delivery_example_pos_rna_matches_readme():
    from rbp_agent.backends.delivery.examples import load_example, own_head_prompt

    ex = load_example("pos")
    assert ex["query"] == "PTBP1"
    assert ex["uniprot"] == "P26599"
    assert ex["path"] == "own_head"
    assert len(ex["rna"]) == 128
    assert ex["rna"].startswith("TTTTGTGGTTGAAAATC")
    prompt = own_head_prompt("pos")
    assert "PTBP1" in prompt
    assert "own-head" in prompt.lower()
    assert ex["rna"] in prompt


def test_resolve_ptbp1_in_panel():
    from rbp_agent.backends.delivery.client import DeliveryToolClient

    r = DeliveryToolClient(offline=True, use_conda=False).call(
        "resolve_rbp", {"query": "PTBP1"}
    )
    assert r.get("in_panel") is True
    assert r.get("alias") == "PTBP1"
    assert r.get("uniprot") == "P26599"
    assert "K562" in (r.get("head_index") or {})


def test_predict_envelope_marks_own_head_path():
    """Unit-level: tool success payload includes path=own_head for single alias."""
    import asyncio
    import json
    from unittest.mock import patch

    from nanobot.agent.tools.rbp.predict import PredictInteractionTool

    PredictInteractionTool.reset_turn_guards()
    tool = PredictInteractionTool()

    fake = {
        "ok": True,
        "predictions": [{"alias": "PTBP1", "prob": 0.966, "head_index": 73, "cohort": "K562"}],
        "cohort": "K562",
        "n_windows": 1,
        "_script": "predict_api.py",
    }

    class _Cli:
        def call(self, name, payload):
            assert name == "rhobind_predict"
            assert payload["rbps"] == ["PTBP1"]
            return fake

    with patch(
        "nanobot.agent.tools.rbp.predict.get_delivery_client",
        return_value=_Cli(),
    ):
        out = asyncio.run(
            tool.execute(rna="ACGU" * 32, rbp_id="PTBP1", cohort="K562")
        )
    env = json.loads(out)
    assert env["status"] == "ok"
    assert env["value"]["path"] == "own_head"
    assert "OWN-HEAD" in env["value"]["stop_hint"]


def test_workspace_skill_sync_copies_always_frontmatter(tmp_path):
    from rbp_agent.integrate import ensure_workspace_skill

    dest = ensure_workspace_skill(tmp_path)
    text = dest.read_text(encoding="utf-8")
    assert "always: true" in text or '"always": true' in text
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "in_panel" in agents
    assert "own-head" in agents.lower() or "own head" in agents.lower()
