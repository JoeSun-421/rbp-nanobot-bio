# -*- coding: utf-8 -*-
"""
P0 tool — predict_interaction
Path: nanobot/agent/tools/rbp/predict.py

nanobot Tool → delivery ``rhobind_predict`` (agent/backbone/predict_api.py).
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters

from nanobot.agent.tools.rbp.common import (
    dumps,
    err,
    get_delivery_client,
    ok,
    resolve_device,
    timed_call,
)


def _predict_cache_key(rna: str, rbps: list[str], cohort: str, device: str) -> str:
    raw = "|".join(
        [
            rna.strip().upper(),
            ",".join(sorted(str(x).upper() for x in rbps)),
            str(cohort or "K562").upper(),
            str(device or "auto").lower(),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "rna": {"type": "string", "description": "RNA sequence (A/C/G/U/T)"},
            "rbp_id": {
                "type": "string",
                "description": "Single RBP alias (e.g. PTBP1); mapped to rbps=[alias]",
            },
            "rbps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of RBP aliases (donors or own head)",
            },
            "cohort": {"type": "string", "enum": ["K562", "HepG2"], "default": "K562"},
            "device": {
                "type": "string",
                "enum": ["auto", "cuda", "cpu"],
                "default": "auto",
                "description": "Prefer cuda when available (ideal GPU env)",
            },
            "aggregate": {"type": "string", "enum": ["max", "mean"], "default": "max"},
        },
        "required": ["rna"],
    }
)
class PredictInteractionTool(Tool):
    """fθ(RNA, RBP) — delivery RhoBind multi-task heads."""

    _plugin_discoverable = True
    _scopes = {"core", "subagent"}
    # Anti-loop: same (rna, rbps, cohort) only runs once per turn.
    _cache: dict[str, str] = {}
    _calls_used: int = 0
    _MAX_CALLS: int = 6  # own head + ≤5 proxies
    _DEFAULT_TIMEOUT_S: int = 180  # fail fast on OOM/hang instead of retry forever

    @property
    def name(self) -> str:
        return "predict_interaction"

    @property
    def description(self) -> str:
        return (
            "RhoBind interaction classifier (delivery rhobind_predict). "
            "OWN-HEAD fast path: after resolve_rbp in_panel=true, call once with "
            "rbp_id=<alias> then STOP and emit JSON (do not transfer). "
            "Unseen RBP: pass rbps=[donor aliases]. "
            "On error/OOM do NOT retry — p_hat=null."
        )

    @property
    def read_only(self) -> bool:
        return True

    @classmethod
    def reset_turn_guards(cls) -> None:
        cls._cache.clear()
        cls._calls_used = 0

    async def execute(self, **kwargs: Any) -> str:
        rna = kwargs.get("rna") or ""
        rbps = kwargs.get("rbps")
        if not rbps and kwargs.get("rbp_id"):
            rbps = [kwargs["rbp_id"]]
        if not rna or not rbps:
            return dumps(err("rna and rbps (or rbp_id) are required"))
        rbps_list = [str(x) for x in list(rbps)]
        cohort = kwargs.get("cohort") or "K562"
        device = resolve_device(kwargs.get("device"))
        key = _predict_cache_key(rna, rbps_list, cohort, device)

        cached = PredictInteractionTool._cache.get(key)
        if cached is not None:
            return cached

        if PredictInteractionTool._calls_used >= PredictInteractionTool._MAX_CALLS:
            out = dumps(
                err(
                    "predict_interaction call budget exhausted this turn; "
                    "do not retry — proceed to verdict with p_hat=null if no probs"
                )
            )
            return out

        def _run():
            client = get_delivery_client(device=device)
            return client.call(
                "rhobind_predict",
                {
                    "rna": rna,
                    "rbps": rbps_list,
                    "cohort": cohort,
                    "device": device,
                    "aggregate": kwargs.get("aggregate") or "max",
                    # delivery subprocess timeout (seconds)
                    "timeout_s": int(
                        kwargs.get("timeout_s")
                        or PredictInteractionTool._DEFAULT_TIMEOUT_S
                    ),
                },
            )

        PredictInteractionTool._calls_used += 1
        try:
            out, ms, error = await asyncio.wait_for(
                asyncio.to_thread(lambda: timed_call(_run)),
                timeout=float(PredictInteractionTool._DEFAULT_TIMEOUT_S) + 30.0,
            )
        except asyncio.TimeoutError:
            result = dumps(
                err(
                    "predict_interaction timed out (likely RhoBind OOM / slow env); "
                    "do not retry — emit verdict with p_hat=null, confidence=low",
                    0.0,
                )
            )
            PredictInteractionTool._cache[key] = result
            return result

        if error:
            result = dumps(
                err(
                    f"{error}; do not retry predict_interaction — "
                    "continue with annotation/similarity evidence, p_hat=null",
                    ms,
                )
            )
            PredictInteractionTool._cache[key] = result
            return result
        if out.get("error") or out.get("ok") is False:
            result = dumps(
                err(
                    f"{out.get('error') or 'rhobind_predict failed'}; "
                    "do not retry — emit verdict with p_hat=null",
                    ms,
                )
            )
            PredictInteractionTool._cache[key] = result
            return result
        preds = out.get("predictions") or []
        # BUILD_SPEC: single in-panel alias = own-head score → Stage-0 path stops.
        path = "own_head" if len(rbps_list) == 1 else "multi_head"
        probs = [
            p.get("prob")
            for p in preds
            if isinstance(p, dict) and p.get("prob") is not None
        ]
        if not probs:
            # e.g. unknown alias / no K562 head — not a successful own-head
            result = dumps(
                ok(
                    {
                        "predictions": preds,
                        "cohort": out.get("cohort"),
                        "n_windows": out.get("n_windows"),
                        "path": path,
                        "prob": None,
                        "stop_hint": (
                            "No usable prob (unknown RBP or no cohort head). "
                            "Do NOT treat as own-head success. "
                            "If resolve_rbp.in_panel=false: transfer with donors that "
                            "have heads, or emit verdict p_hat=null, confidence=low."
                        ),
                        "_delivery_script": out.get("_script"),
                    },
                    ms,
                )
            )
            PredictInteractionTool._cache[key] = result
            return result
        result = dumps(
            ok(
                {
                    "predictions": preds,
                    "cohort": out.get("cohort"),
                    "n_windows": out.get("n_windows"),
                    "path": path,
                    "prob": probs[0] if path == "own_head" else max(probs),
                    "stop_hint": (
                        "OWN-HEAD success: map predictions[0].prob → p_hat/label, "
                        "emit JSON verdict now. Do NOT call transfer/similarity/domain."
                        if path == "own_head"
                        else "Multi-head: continue Stage 3 integrate if proxies."
                    ),
                    "_delivery_script": out.get("_script"),
                },
                ms,
            )
        )
        PredictInteractionTool._cache[key] = result
        return result
