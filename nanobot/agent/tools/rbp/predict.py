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
            "aggregate": {
                "type": "string",
                "enum": ["max", "mean", "weighted"],
                "default": "weighted",
                "description": (
                    "Cross-donor aggregation when multiple rbps are scored. "
                    "'weighted' = proposal §4 Σ s_i·p_i·c_i / Σ s_i·c_i using "
                    "committed LLM similarity_score (c_i defaults to 1.0). "
                    "Window aggregation inside each head stays max/mean at delivery."
                ),
            },
            "force_transfer": {
                "type": "boolean",
                "default": False,
                "description": (
                    "If true, treat target as unseen: refuse single-alias own-head; "
                    "require rbps=[donor aliases with panel heads]."
                ),
            },
            "allow_unseen_own_head": {
                "type": "boolean",
                "default": False,
                "description": "Internal/test override — do not use in product path.",
            },
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
        try:
            from nanobot.agent.tools.rbp.turn_guards import reset_stage_guards

            reset_stage_guards()
        except Exception:
            pass

    async def execute(self, **kwargs: Any) -> str:
        rna = kwargs.get("rna") or ""
        rbps = kwargs.get("rbps")
        if not rbps and kwargs.get("rbp_id"):
            rbps = [kwargs["rbp_id"]]
        if not rna or not rbps:
            return dumps(err("rna and rbps (or rbp_id) are required"))
        rbps_list = [str(x) for x in list(rbps)]
        cohort = kwargs.get("cohort") or "K562"
        force_transfer = bool(kwargs.get("force_transfer"))
        allow_unseen = bool(kwargs.get("allow_unseen_own_head"))

        # Proposal §9.2: never call fθ on an unseen target without proxy donors.
        if not allow_unseen and (force_transfer or len(rbps_list) == 1):
            try:
                from nanobot.agent.tools.rbp.turn_guards import alias_has_panel_head

                if force_transfer and len(rbps_list) == 1:
                    return dumps(
                        err(
                            "force_transfer=true: refuse own-head on a single target; "
                            "pass rbps=[donor aliases with panel heads] only"
                        )
                    )
                if len(rbps_list) == 1 and not alias_has_panel_head(
                    rbps_list[0], cohort=str(cohort)
                ):
                    return dumps(
                        err(
                            f"Unseen / out-of-panel target {rbps_list[0]!r}: "
                            "MUST NOT call predict_interaction as own-head. "
                            "Retrieve proxy donors (seq/domain/structure), then "
                            "predict only on donor aliases that have heads."
                        )
                    )
            except Exception:
                # If registry unavailable, fall through to delivery (will fail soft).
                pass

        # BUILD_SPEC: fuse → confidence_abstain → predict on transfer path.
        try:
            from nanobot.agent.tools.rbp.turn_guards import (
                transfer_predict_blocked_reason,
            )

            blocked_abs = transfer_predict_blocked_reason(
                force_transfer=force_transfer,
                rbps=rbps_list,
                cohort=str(cohort),
            )
            if blocked_abs:
                return dumps(err(blocked_abs))
        except Exception:
            pass

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

        # Cross-donor aggregate mode (proposal §4 weighted). Delivery only
        # accepts max/mean for per-window pooling inside each head.
        cfg_agg = None
        try:
            from nanobot.agent.tools.rbp.common import get_runtime_config

            cfg_agg = (get_runtime_config().get("predict") or {}).get("aggregate")
        except Exception:
            cfg_agg = None
        req_agg = str(kwargs.get("aggregate") or cfg_agg or "weighted")
        delivery_agg = req_agg if req_agg in ("max", "mean") else "max"

        def _run():
            client = get_delivery_client(device=device)
            return client.call(
                "rhobind_predict",
                {
                    "rna": rna,
                    "rbps": rbps_list,
                    "cohort": cohort,
                    "device": device,
                    "aggregate": delivery_agg,
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
        # Proposal §4 Stage 2 return contract: stub confidence + feature_attribution
        # (delivery does not provide saliency / per-head confidence).
        enriched: list[dict[str, Any]] = []
        for p in preds:
            if not isinstance(p, dict):
                continue
            row = dict(p)
            if row.get("confidence") is None:
                row["confidence"] = 1.0
            if "feature_attribution" not in row:
                row["feature_attribution"] = {}
            # Normalize id keys for Stage-3 aggregation matching.
            if not row.get("rbp_id") and row.get("alias"):
                row["rbp_id"] = row["alias"]
            enriched.append(row)
        preds = enriched
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
                        "aggregate": req_agg,
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

        # Cross-donor p_hat: proposal §4 weighted mean when aggregate=weighted.
        p_hat: float | None
        agg_meta: dict[str, Any] | None = None
        if path == "own_head":
            p_hat = float(probs[0])
        elif req_agg == "weighted":
            try:
                from nanobot.agent.tools.rbp.turn_guards import committed_proxies
                from rbp_eval.fuse_hits import aggregate_probability

                proxies = committed_proxies()
                if proxies:
                    agg_meta = aggregate_probability(proxies, preds)
                    p_hat = agg_meta.get("p_hat")
                    if p_hat is None:
                        p_hat = max(probs)
                else:
                    # Should be gated, but fall back safely.
                    p_hat = max(probs)
                    agg_meta = {"fallback": "max", "reason": "no_committed_proxies"}
            except Exception as exc:
                p_hat = max(probs)
                agg_meta = {"fallback": "max", "reason": str(exc)}
        elif req_agg == "mean":
            p_hat = sum(float(x) for x in probs) / len(probs)
        else:
            p_hat = max(probs)

        result = dumps(
            ok(
                {
                    "predictions": preds,
                    "cohort": out.get("cohort"),
                    "n_windows": out.get("n_windows"),
                    "path": path,
                    "prob": p_hat,
                    "aggregate": req_agg,
                    "aggregation": agg_meta,
                    "stop_hint": (
                        "OWN-HEAD success: map predictions[0].prob → p_hat/label, "
                        "emit JSON verdict now. Do NOT call transfer/similarity/domain."
                        if path == "own_head"
                        else (
                            "Multi-head: p_hat from proposal §4 weighted aggregation "
                            "(committed s_i × prob × c_i); continue Stage 3 explanation."
                            if req_agg == "weighted"
                            else "Multi-head: continue Stage 3 integrate if proxies."
                        )
                    ),
                    "_delivery_script": out.get("_script"),
                },
                ms,
            )
        )
        # F2: surface low head-coverage on the transfer path. When donors were
        # requested but some had no cohort head (prob=null), the abstain gate
        # (which only sees retrieval similarity) can still pass — flag it so the
        # verdict forces low confidence and lists it as a caveat.
        if path == "multi_head":
            n_requested = len(rbps_list)
            n_with_head = len(probs)
            n_no_head = n_requested - n_with_head
            if n_no_head > 0 and n_requested > 0:
                coverage = n_with_head / n_requested
                try:
                    from nanobot.agent.tools.rbp.turn_guards import add_evidence_flag

                    add_evidence_flag("low_head_coverage", coverage)
                except Exception:
                    pass
        if path == "own_head":
            try:
                from nanobot.agent.tools.rbp.turn_guards import mark_own_head_success

                mark_own_head_success()
            except Exception:
                pass
        PredictInteractionTool._cache[key] = result
        return result
