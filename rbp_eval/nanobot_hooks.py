# -*- coding: utf-8 -*-
"""
RBPTraceHook as real nanobot.agent.hook.AgentHook (proposal §6–§7).

Records each agent iteration tool calls to JSONL for self-evolution offline.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from nanobot.agent.hook import AgentHook, AgentHookContext


class RBPTraceHook(AgentHook):
    """Write structured traces for self-evolution (proposal §7.1)."""

    def __init__(self, out_path: str | Path, session_key: str = "rbp:default"):
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_key = session_key
        self._t0 = time.time()
        self._buffer: list[dict[str, Any]] = []

    def _write(self, event: dict[str, Any]) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_key": self.session_key,
            **event,
        }
        self._buffer.append(row)
        with open(self.out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def push_event(self, event: dict[str, Any]) -> None:
        """Also used by deterministic RBPAgent path."""
        self._write(event)

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        # capture tool call intents if present on context
        calls = getattr(context, "tool_calls", None) or getattr(context, "pending_tools", None)
        self._write(
            {
                "type": "before_execute_tools",
                "tool_calls": _safe(calls),
            }
        )

    async def after_iteration(self, context: AgentHookContext) -> None:
        self._write(
            {
                "type": "after_iteration",
                "elapsed_s": round(time.time() - self._t0, 3),
                "context_keys": [
                    k for k in dir(context) if not k.startswith("_")
                ][:40],
            }
        )


def _safe(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)
