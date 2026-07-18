# -*- coding: utf-8 -*-
"""Proposal §5 P0 — get_known_rbp_list → delivery rbp_registry.json."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import dumps, err, get_delivery_client, ok, timed_call


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "include_sequences": {"type": "boolean", "default": False},
        },
        "required": [],
    }
)
class GetKnownRBPListTool(Tool):
    _plugin_discoverable = True
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "get_known_rbp_list"

    @property
    def description(self) -> str:
        return (
            "Return catalogue K (238 RBPs) from delivery agent_db/registry/rbp_registry.json."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, include_sequences: bool = False, **_: Any) -> str:
        def _run():
            from backends.delivery.env import apply_delivery_env, load_rbp_registry

            get_delivery_client()  # ensures path + env
            apply_delivery_env()
            reg = load_rbp_registry()
            items = []
            for up, rec in reg.items():
                if not isinstance(rec, dict):
                    continue
                row = {
                    "rbp_id": up,
                    "alias": rec.get("alias"),
                    "cohorts": rec.get("cohorts") or [],
                    "head_index": rec.get("head_index") or {},
                }
                if include_sequences:
                    row["seq_len"] = rec.get("seq_len")
                items.append(row)
            return {"count": len(items), "rbps": items}

        value, ms, error = await asyncio.to_thread(lambda: timed_call(_run))
        if error:
            return dumps(err(error, ms))
        return dumps(ok(value, ms))
