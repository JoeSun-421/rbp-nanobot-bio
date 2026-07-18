"""Stage-1 candidate fusion + Stage-3 numeric aggregation (proposal §4)."""

from __future__ import annotations

from typing import Any, Optional


def fuse_proxy_candidates(
    views: dict[str, list[dict[str, Any]]],
    *,
    n_cand: int = 5,
    tau_drop: float = 0.30,
) -> list[dict[str, Any]]:
    """Deterministic baseline for Stage-1 LLM fusion checkpoint.

    Each output item matches proposal proxy shape (subset):
      rbp_id, similarity_score, similarity_breakdown, rationale
    """
    scores: dict[str, dict[str, float]] = {}
    for view, hits in views.items():
        for h in hits or []:
            rid = h.get("rbp_id") or h.get("uniprot") or h.get("alias")
            if not rid:
                continue
            raw = float(h.get("score") or h.get("similarity") or 0.0)
            # percent-scale identity → [0,1]
            if raw > 1.0 + 1e-9:
                raw = raw / 100.0
            scores.setdefault(rid, {})
            scores[rid][view] = max(0.0, min(1.0, raw))

    fused: list[dict[str, Any]] = []
    for rid, br in scores.items():
        # simple mean of available views
        vals = list(br.values())
        sim = sum(vals) / len(vals) if vals else 0.0
        if sim < tau_drop:
            continue
        fused.append(
            {
                "rbp_id": rid,
                "similarity_score": round(sim, 4),
                "similarity_breakdown": br,
                "rationale": f"deterministic mean over views {sorted(br)}",
            }
        )
    fused.sort(key=lambda x: x["similarity_score"], reverse=True)
    return fused[:n_cand]


def aggregate_probability(
    proxies: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    """p_hat = sum(s_i * p_i * c_i) / sum(s_i * c_i)  (proposal Stage 3)."""
    pred_by = {p.get("rbp_id") or p.get("alias"): p for p in predictions}
    num = den = 0.0
    parts = []
    for px in proxies:
        rid = px["rbp_id"]
        s = float(px.get("similarity_score") or 0.0)
        pr = pred_by.get(rid) or {}
        p = pr.get("prob")
        if p is None:
            continue
        c = float(pr.get("confidence") if pr.get("confidence") is not None else 1.0)
        w = s * c
        num += w * float(p)
        den += w
        parts.append({"rbp_id": rid, "s": s, "p": float(p), "c": c, "w": w})
    p_hat = (num / den) if den > 0 else None
    return {"p_hat": None if p_hat is None else round(p_hat, 6), "terms": parts}


def label_from_p_hat(
    p_hat: Optional[float],
    thresholds: Optional[dict[str, float]] = None,
) -> str:
    thr = thresholds or {"strong": 0.75, "likely": 0.50, "unlikely": 0.25}
    if p_hat is None:
        return "Unknown"
    if p_hat >= thr["strong"]:
        return "Strong"
    if p_hat >= thr["likely"]:
        return "Likely"
    if p_hat >= thr["unlikely"]:
        return "Unlikely"
    return "No"
