# -*- coding: utf-8 -*-
"""Register curated RBP tools + optional raw delivery tools onto a ToolRegistry."""

from __future__ import annotations

from typing import Optional, Union

from nanobot.agent.tools.registry import ToolRegistry

from nanobot.agent.tools.rbp import register_all as register_proposal_tools

RawMode = Union[bool, str]


def _normalize_raw_mode(include_raw_delivery: RawMode) -> str:
    """Map API → none | whitelist | all. Default for True is whitelist (MVP)."""
    if include_raw_delivery is False or include_raw_delivery in ("none", "false", 0):
        return "none"
    if include_raw_delivery == "all":
        return "all"
    # True / "whitelist" / anything else → whitelist
    return "whitelist"


def register_rbp_tools(
    registry: Optional[ToolRegistry] = None,
    *,
    include_raw_delivery: RawMode = "whitelist",
) -> tuple[ToolRegistry, list[str]]:
    """
    Register RBP tools onto a Nanobot ToolRegistry.

    ``include_raw_delivery``:
      - ``"whitelist"`` / ``True`` — Stage 0/3 extras only (default; avoids lit loops)
      - ``"all"`` — every delivery SCRIPT_MAP tool
      - ``False`` / ``"none"`` — curated P0–P2 tools only

    Returns (registry, registered_names).
    """
    reg = registry if registry is not None else ToolRegistry()
    names = register_proposal_tools(reg)
    mode = _normalize_raw_mode(include_raw_delivery)

    if mode != "none":
        from nanobot.agent.tools.rbp.common import (
            ensure_nanobot_bio_on_path,
            get_delivery_client,
        )
        from rbp_agent.backends.delivery.registry import (
            STAGE_RAW_WHITELIST,
            build_delivery_raw_tools,
        )

        ensure_nanobot_bio_on_path()
        client = get_delivery_client()
        existing = set(names)
        allow = None if mode == "all" else STAGE_RAW_WHITELIST
        for t in build_delivery_raw_tools(client, allow_names=allow):
            if t.name not in existing:
                reg.register(t)
                names.append(t.name)
                existing.add(t.name)

    # Re-export for callers that imported STAGE_RAW_WHITELIST from here
    return reg, names


# Back-compat alias (canonical: rbp_agent.backends.delivery.registry)
def __getattr__(name: str):
    if name == "STAGE_RAW_WHITELIST":
        from rbp_agent.backends.delivery.registry import STAGE_RAW_WHITELIST as _w

        return _w
    raise AttributeError(name)
