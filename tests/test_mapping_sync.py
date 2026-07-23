# -*- coding: utf-8 -*-
"""mapping.yaml covers SCRIPT_MAP whitelist + curated tool wrappers."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_mapping_covers_stage_whitelist_and_proposal():
    from app.backends.delivery.client import SCRIPT_MAP
    from app.backends.delivery.registry import PROPOSAL_TOOL_NAMES, STAGE_RAW_WHITELIST

    mapping = yaml.safe_load(
        (ROOT / "app" / "backends" / "delivery" / "mapping.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(mapping, dict)

    for name in STAGE_RAW_WHITELIST:
        assert name in mapping, f"whitelist tool {name} missing from mapping.yaml"
        assert name in SCRIPT_MAP, f"whitelist tool {name} missing from SCRIPT_MAP"

    for name in PROPOSAL_TOOL_NAMES:
        assert name in mapping, f"curated tool {name} missing from mapping.yaml"
