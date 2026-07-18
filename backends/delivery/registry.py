# -*- coding: utf-8 -*-
"""Nanobot ToolRegistry bridge for delivery (whitelist + proposal install).

P0–P2 proposal tools are **delegated** to ``nanobot.agent.tools.rbp``
(under ``nanobot/agent/tools/rbp/``). This module only builds Stage 0/3 raw
delivery tools and registration helpers.

Canonical import: ``from backends.delivery.registry import register_tools``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional, Union


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nanobot.agent.tools.base import Tool  # noqa: E402
from nanobot.agent.tools.registry import ToolRegistry  # noqa: E402

from backends.delivery.client import (  # noqa: E402
    DeliveryToolClient,
    SCRIPT_MAP,
    tools_meta_by_name,
)
from backends.delivery.env import apply_delivery_env  # noqa: E402

# Stage 0 / 3 extras for MVP agent (proposal P0–P2 registered separately).
STAGE_RAW_WHITELIST: frozenset[str] = frozenset(
    {
        "resolve_rbp",
        "domain_architecture",
        "structure_fetch",
        "rna_preprocess",
        "similarity_weighted_vote",
        "transfer_prior_lookup",
        "donor_quality_prior",
        "confidence_abstain",
    }
)

# Proposal Table 2 names (implemented in nanobot.agent.tools.rbp).
PROPOSAL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "predict_interaction",
        "get_known_rbp_list",
        "seq_similarity",
        "struct_similarity",
        "get_func_annotation",
        "predict_structure",
        "literature_search",
    }
)

# Back-compat alias used by older code that inspected SPECS.
PROPOSAL_TOOL_SPECS: list[dict[str, Any]] = [
    {"name": n} for n in sorted(PROPOSAL_TOOL_NAMES)
]


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _envelope_ok(value: Any, latency_ms: float = 0.0) -> dict[str, Any]:
    return {"status": "ok", "value": value, "latency_ms": latency_ms}


def _envelope_err(reason: str, latency_ms: float = 0.0) -> dict[str, Any]:
    return {"status": "error", "reason": str(reason), "latency_ms": latency_ms}


def _normalize_delivery_payload(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Coerce common LLM arg shapes to what delivery scripts expect.

    Does not edit delivery source — only the bridge payload.
    """
    out = dict(payload)
    if name == "similarity_weighted_vote":
        preds = out.get("predictions")
        # LLM often passes {"PTBP1": 0.96, ...}; script expects
        # [{"donor"|"alias": str, "prob": float}, ...]
        if isinstance(preds, dict):
            out["predictions"] = [
                {"donor": str(k), "prob": float(v)}
                for k, v in preds.items()
                if v is not None
            ]
        # priors / quality sometimes passed as list of {donor, auprc}
        for key in ("transfer_priors", "donor_quality"):
            raw = out.get(key)
            if isinstance(raw, list):
                mapped: dict[str, Any] = {}
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    d = item.get("donor") or item.get("alias")
                    if d is None:
                        continue
                    val = item.get("auprc")
                    if val is None:
                        val = item.get("score")
                    if val is not None:
                        mapped[str(d)] = val
                out[key] = mapped
    return out


class DeliveryBackedTool(Tool):
    """Generic wrapper: nanobot Tool → DeliveryToolClient.call."""

    _plugin_discoverable = False
    _scopes = {"core", "subagent"}

    def __init__(
        self,
        *,
        tool_name: str,
        description: str,
        parameters: dict[str, Any],
        client: DeliveryToolClient,
        delivery_name: Optional[str] = None,
        read_only: bool = True,
    ):
        self._name = tool_name
        self._description = description
        self._parameters = parameters
        self._client = client
        self._delivery_name = delivery_name or tool_name
        self._read_only = read_only

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return dict(self._parameters)

    @property
    def read_only(self) -> bool:
        return self._read_only

    async def execute(self, **kwargs: Any) -> str:
        payload = {k: v for k, v in kwargs.items() if v is not None}
        payload = _normalize_delivery_payload(self._delivery_name, payload)

        def _run() -> dict[str, Any]:
            return self._client.call(self._delivery_name, payload)

        try:
            out = await asyncio.to_thread(_run)
        except Exception as e:  # noqa: BLE001
            return _dumps(_envelope_err(f"{type(e).__name__}: {e}"))

        ms = float(out.get("_latency_ms") or 0.0)
        if out.get("skipped") or (
            out.get("ok") is False and out.get("error")
        ):
            return _dumps(
                _envelope_err(out.get("error") or out.get("reason") or "tool failed", ms)
            )

        clean = {
            k: v
            for k, v in out.items()
            if not str(k).startswith("_") and k not in ("ok",)
        }
        env = _envelope_ok(clean, ms)
        env["_meta"] = {
            "delivery_tool": self._delivery_name,
            "script": out.get("_script"),
            "invocation": out.get("_invocation"),
        }
        return _dumps(env)


def _default_client(
    *, offline: bool = False, device: str = "cpu", use_conda: bool = True
) -> DeliveryToolClient:
    apply_delivery_env()
    return DeliveryToolClient(offline=offline, device=device, use_conda=use_conda)


def build_proposal_tools(client: Optional[DeliveryToolClient] = None) -> list[Tool]:
    """Instantiate P0–P2 from installed ``nanobot.agent.tools.rbp`` (single source)."""
    del client  # rbp tools use their own DeliveryToolClient via common.py
    try:
        from nanobot.agent.tools.rbp import ALL_RBP_TOOL_CLASSES
    except ImportError:
        # Ensure tools are installed into the real nanobot tree, then retry
        try:
            from integrate import install_rbp_tools_into_nanobot

            install_rbp_tools_into_nanobot()
        except Exception:
            pass
        from nanobot.agent.tools.rbp import ALL_RBP_TOOL_CLASSES

    return [cls() for cls in ALL_RBP_TOOL_CLASSES]


def build_delivery_raw_tools(
    client: Optional[DeliveryToolClient] = None,
    *,
    allow_names: Optional[set[str] | frozenset[str]] = None,
) -> list[Tool]:
    """
    Register BUILD_SPEC delivery tool names for the nanobot LLM.

    If ``allow_names`` is set, only those names are registered (MVP whitelist).
    """
    client = client or _default_client()
    meta = tools_meta_by_name()
    tools: list[Tool] = []
    for name, rel in SCRIPT_MAP.items():
        if name in PROPOSAL_TOOL_NAMES:
            continue
        if allow_names is not None and name not in allow_names:
            continue
        m = meta.get(name, {})
        params: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }
        ischema = m.get("input_schema") or {}
        if isinstance(ischema, dict):
            props: dict[str, Any] = {}
            for k, v in ischema.items():
                if v == "str":
                    props[k] = {"type": "string"}
                elif v == "int":
                    props[k] = {"type": "integer"}
                elif v == "float":
                    props[k] = {"type": "number"}
                elif v == "bool":
                    props[k] = {"type": "boolean"}
                else:
                    props[k] = {}
            if props:
                params["properties"] = props
        desc = str(m.get("summary") or f"Delivery tool {name} ({rel})")
        if name == "similarity_weighted_vote":
            desc += (
                " Args: predictions=[{donor|alias, prob}, ...] "
                "(list of objects, not a {alias:prob} map); "
                "hits=[{alias, score}, ...]."
            )
        elif name == "domain_architecture":
            desc += (
                " Prefer alias/uniprot for known RBPs (fast registry). "
                "For novel sequences, domains=[] unless network=true "
                "(InterProScan REST — minutes). Never pass RNA as sequence."
            )
        tools.append(
            DeliveryBackedTool(
                tool_name=name,
                description=desc,
                parameters=params,
                client=client,
                delivery_name=name,
                read_only=True,
            )
        )
    return tools


def build_all_tools(
    client: Optional[DeliveryToolClient] = None,
    *,
    include_raw_delivery: Union[bool, str] = "whitelist",
) -> list[Tool]:
    client = client or _default_client()
    tools = build_proposal_tools(client)
    mode = include_raw_delivery
    if mode is False or mode in ("none", "false"):
        return tools
    if mode == "all":
        tools.extend(build_delivery_raw_tools(client, allow_names=None))
    else:
        tools.extend(
            build_delivery_raw_tools(client, allow_names=STAGE_RAW_WHITELIST)
        )
    return tools


ALL_TOOL_NAMES: list[str] = []


def register_tools(
    registry: ToolRegistry,
    client: Optional[DeliveryToolClient] = None,
    *,
    include_raw_delivery: Union[bool, str] = "whitelist",
) -> list[str]:
    """Register onto nanobot ToolRegistry; return registered names."""
    global ALL_TOOL_NAMES
    tools = build_all_tools(client, include_raw_delivery=include_raw_delivery)
    names = []
    for t in tools:
        registry.register(t)
        names.append(t.name)
    ALL_TOOL_NAMES = names
    return names
