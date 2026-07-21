"""Retrieval fusion helpers: multi-axis RbpHit merge, Stage-1 proxies, Stage-3 aggregation."""

from __future__ import annotations

from typing import Any, Optional


DEFAULT_WEIGHTS = {
    "esmc_cosine": 1.0,
    "esm2_cosine": 0.5,
    "domain_jaccard": 0.6,
    "domain_overlap": 0.6,
    "seq_identity": 0.3,
    "tm_score": 0.3,
    "lddt": 0.3,
    "fident": 0.2,
    "saprot_cosine": 0.0,
    "function_similarity": 0.4,
    "rna_embed": 0.3,
    "rna_fm": 0.3,
}


def _rank_normalize(scores: dict[str, float]) -> dict[str, float]:
    """Per-metric rank normalize to (0,1] across aliases."""
    if not scores:
        return {}
    ordered = sorted(scores.items(), key=lambda x: x[1])
    n = len(ordered)
    out = {}
    for i, (alias, _s) in enumerate(ordered):
        out[alias] = (i + 1) / n
    return out


def fuse_rbp_hits(
    hit_lists: list[list[dict[str, Any]]],
    *,
    weights: Optional[dict[str, float]] = None,
    top_k: int = 5,
    exclude_aliases: Optional[set[str]] = None,
    allowed_aliases: Optional[set[str]] = None,
    use_rank_normalize: bool = True,
    tau_drop: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Merge RbpHit[] lists into ranked donors with fused score.

    If ``tau_drop`` is set (Stage 1 floor), drop donors with fused
    score below that threshold before applying ``top_k``.
    """
    wmap = {**DEFAULT_WEIGHTS, **(weights or {})}
    exclude_aliases = exclude_aliases or set()
    acc: dict[str, dict[str, Any]] = {}
    for hits in hit_lists:
        for h in hits or []:
            alias = h.get("alias")
            if not alias or alias in exclude_aliases:
                continue
            if allowed_aliases is not None and alias not in allowed_aliases:
                continue
            metric = str(h.get("metric") or "unknown")
            score = float(h.get("score") or 0.0)
            # Normalize percent-scale identity (0–100) to [0,1] before clamp
            if score > 1.0 + 1e-9 and (
                "identity" in metric.lower()
                or metric in ("seq_identity", "fident", "pident")
            ):
                score = score / 100.0
            score = max(0.0, min(1.0, score))
            slot = acc.setdefault(
                alias,
                {"alias": alias, "uniprot": h.get("uniprot") or "", "metrics": {}},
            )
            if h.get("uniprot"):
                slot["uniprot"] = h["uniprot"]
            prev = slot["metrics"].get(metric)
            if prev is None or score > prev:
                slot["metrics"][metric] = score

    if not acc:
        return []

    metrics_present: set[str] = set()
    for slot in acc.values():
        metrics_present |= set(slot["metrics"].keys())

    normed: dict[str, dict[str, float]] = {a: {} for a in acc}
    for m in metrics_present:
        col = {a: slot["metrics"][m] for a, slot in acc.items() if m in slot["metrics"]}
        if use_rank_normalize and len(col) > 1:
            rn = _rank_normalize(col)
            for a, raw in col.items():
                normed[a][m] = 0.5 * raw + 0.5 * rn[a]
        else:
            for a, raw in col.items():
                normed[a][m] = raw

    fused: list[dict[str, Any]] = []
    for alias, slot in acc.items():
        metrics = normed.get(alias) or {}
        num = den = 0.0
        for m, s in metrics.items():
            w = float(wmap.get(m, 0.2))
            if w <= 0:
                continue
            num += w * s
            den += w
        if den <= 0:
            continue
        fused_score = num / den
        fused.append(
            {
                "alias": alias,
                "uniprot": slot.get("uniprot") or "",
                "score": round(fused_score, 4),
                "metric": "fused",
                "rank": 0,
                "sim_by_modality": {
                    k: round(v, 4) for k, v in (slot.get("metrics") or {}).items()
                },
                "sim_normalized": {k: round(v, 4) for k, v in metrics.items()},
            }
        )
    fused.sort(key=lambda x: x["score"], reverse=True)
    if tau_drop is not None:
        fused = [r for r in fused if float(r.get("score") or 0) >= float(tau_drop)]
    for i, row in enumerate(fused[:top_k], start=1):
        row["rank"] = i
    return fused[:top_k]


def fuse_proxy_candidates(
    views: dict[str, list[dict[str, Any]]],
    *,
    n_cand: int = 5,
    tau_drop: float = 0.30,
) -> list[dict[str, Any]]:
    """Deterministic baseline for Stage-1 LLM fusion checkpoint.

    Each output item matches the proxy schema (subset):
      rbp_id, similarity_score, similarity_breakdown, rationale
    """
    scores: dict[str, dict[str, float]] = {}
    for view, hits in views.items():
        for h in hits or []:
            rid = h.get("rbp_id") or h.get("uniprot") or h.get("alias")
            if not rid:
                continue
            raw = float(h.get("score") or h.get("similarity") or 0.0)
            if raw > 1.0 + 1e-9:
                raw = raw / 100.0
            scores.setdefault(rid, {})
            scores[rid][view] = max(0.0, min(1.0, raw))

    fused: list[dict[str, Any]] = []
    for rid, br in scores.items():
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
    """p_hat = sum(s_i * p_i * c_i) / sum(s_i * c_i)  (Stage 3 aggregation)."""
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
    """Delegate to App SoT (``verdict_schema``) so label cuts stay single-sourced."""
    from rbp_agent.core.verdict_schema import label_from_p_hat as _label

    return _label(p_hat, thresholds)
