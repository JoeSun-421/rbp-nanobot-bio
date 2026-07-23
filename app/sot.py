# -*- coding: utf-8 -*-
"""Locate plugin SoT (skills + tools/rbp) for overlay sync.

Single source of truth: ``plugin/nanobot/`` under ``NANOBOT_BIO_ROOT``.
"""

from __future__ import annotations

import os
from pathlib import Path


def sot_root() -> Path:
    """Return the SoT directory (contains ``skills/`` and ``agent/tools/rbp/``)."""
    bio = Path(
        os.environ.get("NANOBOT_BIO_ROOT", Path(__file__).resolve().parents[1])
    ).expanduser().resolve()
    return bio / "plugin" / "nanobot"


def skill_md() -> Path:
    return sot_root() / "skills" / "rbp-agent" / "SKILL.md"


def tools_rbp() -> Path:
    return sot_root() / "agent" / "tools" / "rbp"
