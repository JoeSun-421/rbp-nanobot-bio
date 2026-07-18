"""Multi-axis RbpHit fusion (AGENT_BUILD_SPEC §4 + §9 normalize; DESIGN weights)."""

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
}


def _rank_normalize(scores: dict[str, float]) -> dict[str, float]:
    """Per-metric rank normalize to (0,1] across aliases (SPEC §9)."""
    if not scores:
        return {}
    # higher score → higher rank value
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

    If ``tau_drop`` is set (proposal Stage 1 floor), drop donors with fused
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

    # per-metric rank normalize across donors
    metrics_present: set[str] = set()
    for slot in acc.values():
        metrics_present |= set(slot["metrics"].keys())

    normed: dict[str, dict[str, float]] = {a: {} for a in acc}
    for m in metrics_present:
        col = {a: slot["metrics"][m] for a, slot in acc.items() if m in slot["metrics"]}
        if use_rank_normalize and len(col) > 1:
            rn = _rank_normalize(col)
            # blend raw and rank to keep absolute signal (ESM 0.96 vs 0.55)
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
