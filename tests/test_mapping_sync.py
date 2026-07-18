# -*- coding: utf-8 -*-
"""mapping.yaml must cover SCRIPT_MAP whitelist + proposal wrappers."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_mapping_covers_stage_whitelist_and_proposal():
    from backends.delivery.client import SCRIPT_MAP
    from backends.delivery.registry import PROPOSAL_TOOL_NAMES, STAGE_RAW_WHITELIST

    mapping = yaml.safe_load(
        (ROOT / "backends" / "delivery" / "mapping.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(mapping, dict)

    for name in STAGE_RAW_WHITELIST:
        assert name in mapping, f"whitelist tool {name} missing from mapping.yaml"
        assert name in SCRIPT_MAP, f"whitelist tool {name} missing from SCRIPT_MAP"

    for name in PROPOSAL_TOOL_NAMES:
        assert name in mapping, f"proposal tool {name} missing from mapping.yaml"
