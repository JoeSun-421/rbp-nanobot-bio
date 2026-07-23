# -*- coding: utf-8 -*-
"""Nanobot ToolRegistry bridge for delivery (whitelist + curated tool install).

Curated P0–P2 tools are **delegated** to ``nanobot.agent.tools.rbp``
(under ``nanobot/agent/tools/rbp/``). This module only builds Stage 0/3 raw
delivery tools and registration helpers.

Canonical import: ``from app.backends.delivery.registry import register_tools``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional, Union


_ROOT = Path(__file__).resolve().parents[3]  # nanobot-bio repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nanobot.agent.tools.base import Tool  # noqa: E402
from nanobot.agent.tools.registry import ToolRegistry  # noqa: E402

from app.backends.delivery.client import (  # noqa: E402
    DeliveryToolClient,
    SCRIPT_MAP,
    tools_meta_by_name,
)
from app.backends.delivery.env import apply_delivery_env  # noqa: E402

# Narrow MVP extras (curated P0–P2 registered separately). Final product uses mode=all.
STAGE_RAW_WHITELIST: frozenset[str] = frozenset(
    {
        "resolve_rbp",
        "domain_architecture",
        "structure_fetch",
        "structure_consensus",
        "pdb_metadata",
        "rna_preprocess",
        "rna_blastn",
        "function_category",
        "go_pfam_lookup",
        "colabfold_msa",
        "esm_embed",
        "pymol_util",
        "similarity_weighted_vote",
        "transfer_prior_lookup",
        "donor_quality_prior",
        "confidence_abstain",
    }
)

# Proposal Table 2 / curated agent names (implemented in nanobot.agent.tools.rbp).
PROPOSAL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "predict_interaction",
        "get_known_rbp_list",
        "seq_similarity",
        "struct_similarity",
        "get_func_annotation",
        "predict_structure",
        "literature_search",
        "lookup_proxy_cache",
        "fuse_similarity_views",
        "rna_similarity",
        "check_near_known",
    }
)

# Delivery SCRIPT_MAP names already covered by curated wrappers (avoid duplicate
# registrations under the same science path). Raw aliases stay available when
# they differ from curated names (e.g. esm_similarity vs seq_similarity).
CURATED_COVERED_DELIVERY: frozenset[str] = frozenset(
    {
        "rhobind_predict",  # predict_interaction
        "uniprot_annotation",  # get_func_annotation (also merges category/pdb)
        "structure_predict_af3",  # predict_structure
        "literature_retrieval",  # literature_search (anti-loop curated)
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
        # LLM may put scores on predictions but leave hits empty — copy scores → hits
        hits = out.get("hits")
        if (not hits) and isinstance(out.get("predictions"), list):
            synth = []
            for item in out["predictions"]:
                if not isinstance(item, dict):
                    continue
                d = item.get("donor") or item.get("alias")
                sc = item.get("similarity") or item.get("score") or item.get("sim")
                if d is not None and sc is not None:
                    try:
                        synth.append({"alias": str(d), "score": float(sc)})
                    except (TypeError, ValueError):
                        pass
            if synth:
                out["hits"] = synth
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
    elif name == "domain_architecture":
        # Inject catalogue AA so InterProScan can run when caller sets network=true.
        # Do NOT auto-enable network (InterProScan is minutes-long).
        if not out.get("sequence"):
            try:
                from nanobot.agent.tools.rbp.common import load_catalogue_sequence

                for key in ("alias", "uniprot", "query", "rbp_id"):
                    q = out.get(key)
                    if q:
                        seq = load_catalogue_sequence(str(q))
                        if seq:
                            out["sequence"] = seq
                            break
            except Exception:
                pass
    elif name == "structure_fetch":
        if not out.get("uniprot") and out.get("alias"):
            out.setdefault("query", out["alias"])
        if not out.get("uniprot") and out.get("query"):
            out.setdefault("uniprot", out["query"])
    elif name == "resolve_rbp":
        if not out.get("query"):
            out["query"] = out.get("alias") or out.get("uniprot") or out.get("rbp_id") or ""
    elif name == "confidence_abstain":
        # Auto-inject evolved/default abstain floors; explicit LLM thresholds win.
        try:
            from app.core.runtime_config import abstain_thresholds

            cfg_thr = abstain_thresholds()
            user_thr = out.get("thresholds")
            if isinstance(user_thr, dict) and user_thr:
                merged = {**cfg_thr, **{str(k): float(v) for k, v in user_thr.items()}}
                out["thresholds"] = merged
            else:
                out["thresholds"] = dict(cfg_thr)
        except Exception:
            pass
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
        try:
            from nanobot.agent.tools.rbp.turn_guards import retrieve_blocked_reason

            blocked = retrieve_blocked_reason(self._name)
            if blocked:
                return _dumps(_envelope_err(blocked))
        except Exception:
            pass
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
        # Enrich resolve with catalogue AA so transfer tools need no scrape/read_file
        if self._delivery_name == "resolve_rbp":
            if clean.get("matched"):
                try:
                    from nanobot.agent.tools.rbp.common import load_catalogue_sequence

                    q = (
                        clean.get("uniprot")
                        or clean.get("alias")
                        or payload.get("query")
                        or ""
                    )
                    seq = load_catalogue_sequence(str(q)) if q else None
                    if seq:
                        clean["sequence"] = seq
                        clean["seq_len"] = len(seq)
                except Exception:
                    pass
            else:
                clean["hint"] = (
                    "Not in RhoBind catalogue. Do not expect own-head. "
                    "For transfer: need AA sequence (seq_similarity with UniProt "
                    "accession auto-fetches from UniProt REST) + donors with heads; "
                    "else emit p_hat=null, confidence=low. Do not invent sequences."
                )
        if (
            self._delivery_name == "domain_architecture"
            and (clean.get("domain_source") == "none" or not clean.get("query_domains"))
        ):
            clean["hint"] = (
                "No registry Pfam for this RBP. Re-call with network=true "
                "(and sequence is auto-filled from catalogue) for InterProScan — slow."
            )
        env = _envelope_ok(clean, ms)
        env["_meta"] = {
            "delivery_tool": self._delivery_name,
            "script": out.get("_script"),
            "invocation": out.get("_invocation"),
        }
        if self._delivery_name == "confidence_abstain":
            try:
                from nanobot.agent.tools.rbp.turn_guards import mark_abstain_done

                mark_abstain_done()
            except Exception:
                pass
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
            from app.integrate import install_rbp_tools_into_nanobot

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
        if name in PROPOSAL_TOOL_NAMES or name in CURATED_COVERED_DELIVERY:
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
    include_raw_delivery: Union[bool, str] = "all",
) -> list[Tool]:
    client = client or _default_client()
    tools = build_proposal_tools(client)
    mode = include_raw_delivery
    if mode is False or mode in ("none", "false"):
        return tools
    if mode in ("all", "all_ready", "ready", True):
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
    include_raw_delivery: Union[bool, str] = "all",
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
