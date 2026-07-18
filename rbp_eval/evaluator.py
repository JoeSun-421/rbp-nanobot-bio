# -*- coding: utf-8 -*-
"""
Proposal §7 + §9 — self-evolution evaluator.

1. Tool attribution from supporting_rbps / retrieval modalities
2. Weight & threshold re-tuning on D_val (LOO transfer AUPRC as proxy objective)
3. Toolkit expansion proposals from systematic failure modes
4. Orchestrator: run_self_evolution() writes evolved config + report
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from rbp_eval.fuse_hits import DEFAULT_WEIGHTS, fuse_rbp_hits
from rbp_eval.proxy_cache import promote_from_traces

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PACKAGE_ROOT / "config" / "defaults.yaml"
EVOLVED_CONFIG = PACKAGE_ROOT / "config" / "evolved.yaml"
EVOLVED_REPORT = PACKAGE_ROOT / "out" / "self_evolution_report.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvolutionReport:
    n_traces: int = 0
    n_val: int = 0
    tool_attribution: dict[str, Any] = field(default_factory=dict)
    weight_retune: dict[str, Any] = field(default_factory=dict)
    threshold_retune: dict[str, Any] = field(default_factory=dict)
    toolkit_proposals: list[dict[str, Any]] = field(default_factory=list)
    cache_promotion: dict[str, Any] = field(default_factory=dict)
    evolved_config_path: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# §7.2 Tool attribution
# ---------------------------------------------------------------------------

def tool_attribution(
    results: list[dict[str, Any]],
    *,
    min_support_fraction: float = 0.05,
) -> dict[str, Any]:
    """
    Recover which evidence channels / tools supported correct (or any) verdicts.

    Uses:
      - evidence_table[].sim_by_modality keys
      - retrieval.* ok flags
      - supporting_rbps presence
    """
    modality_counts: dict[str, float] = {}
    tool_counts: dict[str, float] = {}
    n = 0
    n_with_support = 0

    for r in results:
        n += 1
        et = r.get("evidence_table") or []
        ret = r.get("retrieval") or {}
        verdict = r.get("verdict") or {}
        supporting = verdict.get("supporting_rbps") or []

        if supporting or et:
            n_with_support += 1

        # modality mass from evidence table
        for row in et:
            sims = row.get("sim_by_modality") or {}
            for mod, sc in sims.items():
                try:
                    w = float(sc)
                except (TypeError, ValueError):
                    w = 1.0
                modality_counts[mod] = modality_counts.get(mod, 0.0) + max(w, 0.0)

        # tool success counts
        for tname, meta in ret.items():
            if isinstance(meta, dict) and meta.get("ok"):
                tool_counts[tname] = tool_counts.get(tname, 0.0) + 1.0
            elif isinstance(meta, dict) and meta.get("error"):
                tool_counts[tname] = tool_counts.get(tname, 0.0)  # explicit 0 bump skip

        # integration tools used
        integ = r.get("integration") or {}
        if integ.get("contributions") is not None:
            tool_counts["similarity_weighted_vote"] = (
                tool_counts.get("similarity_weighted_vote", 0.0) + 1.0
            )
        if integ.get("transfer_priors"):
            tool_counts["transfer_prior_lookup"] = (
                tool_counts.get("transfer_prior_lookup", 0.0) + 1.0
            )
        if integ.get("donor_quality"):
            tool_counts["donor_quality_prior"] = (
                tool_counts.get("donor_quality_prior", 0.0) + 1.0
            )

    # normalize
    mod_sum = sum(modality_counts.values()) or 1.0
    tool_sum = sum(tool_counts.values()) or 1.0
    mod_frac = {k: round(v / mod_sum, 4) for k, v in sorted(modality_counts.items())}
    tool_frac = {k: round(v / tool_sum, 4) for k, v in sorted(tool_counts.items())}

    # retirement candidates: tools registered in retrieval but low fraction
    retire = [
        t
        for t, f in tool_frac.items()
        if f < min_support_fraction and t not in ("resolve_rbp",)
    ]

    return {
        "n_results": n,
        "n_with_support": n_with_support,
        "modality_mass": mod_frac,
        "tool_success_fraction": tool_frac,
        "retirement_candidates": retire,
        "note": (
            "Low-attribution tools are candidates for retirement or skill demotion; "
            "human review required before removing from registry."
        ),
    }


# ---------------------------------------------------------------------------
# §7.3 Weight & threshold re-tuning
# ---------------------------------------------------------------------------

def _load_loo_matrix() -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], float]]:
    import csv

    from backends.delivery.env import apply_delivery_env, resolve_delivery_paths

    apply_delivery_env()
    paths = resolve_delivery_paths()
    summary_p = paths["agent_db"] / "transfer" / "loo_summary.csv"
    metrics_p = paths["agent_db"] / "transfer" / "loo_transfer_metrics.csv"
    if not summary_p.is_file():
        summary_p = (
            paths["delivery_root"]
            / "agent"
            / "database"
            / "transfer"
            / "loo_summary.csv"
        )
    if not metrics_p.is_file():
        metrics_p = (
            paths["delivery_root"]
            / "agent"
            / "database"
            / "transfer"
            / "loo_transfer_metrics.csv"
        )

    summary: dict[str, dict[str, Any]] = {}
    if summary_p.is_file():
        with open(summary_p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                summary[r["held_rbp"]] = r

    matrix: dict[tuple[str, str], float] = {}
    if metrics_p.is_file():
        with open(metrics_p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                matrix[(r["held_rbp"], r["foreign_rbp"])] = float(r["auprc"])
    return summary, matrix


def _policy_score(
    held: str,
    hit_lists: list[list[dict[str, Any]]],
    matrix: dict[tuple[str, str], float],
    weights: dict[str, float],
    top_k: int,
) -> Optional[float]:
    donors = fuse_rbp_hits(
        hit_lists,
        weights=weights,
        top_k=top_k,
        exclude_aliases={held},
        use_rank_normalize=True,
    )
    vals = []
    for d in donors:
        a = matrix.get((held, d["alias"]))
        if a is not None:
            vals.append(float(a))
    if not vals:
        return None
    # objective: mean of top-k measured transfer AUPRC (proxy for calibrated CE)
    return sum(vals) / len(vals)


def retune_weights(
    held_to_hit_lists: dict[str, list[list[dict[str, Any]]]],
    *,
    base_weights: Optional[dict[str, float]] = None,
    top_k: int = 5,
    grid: Optional[list[float]] = None,
) -> dict[str, Any]:
    """
    Coordinate-wise grid search over fusion weights to maximise mean LOO
    transfer AUPRC of the fused donor policy (proposal §7.3 / §9).
    """
    _, matrix = _load_loo_matrix()
    weights = {**DEFAULT_WEIGHTS, **(base_weights or {})}
    grid = grid or [0.0, 0.3, 0.6, 1.0, 1.5]

    def mean_obj(w: dict[str, float]) -> tuple[float, int]:
        scores = []
        for held, lists in held_to_hit_lists.items():
            s = _policy_score(held, lists, matrix, w, top_k)
            if s is not None:
                scores.append(s)
        if not scores:
            return 0.0, 0
        return sum(scores) / len(scores), len(scores)

    base_score, n = mean_obj(weights)
    best = dict(weights)
    best_score = base_score
    history = [{"step": "init", "score": base_score, "n": n, "weights": dict(weights)}]

    # tune keys that appear in DEFAULT_WEIGHTS and matter for offline LOO
    tune_keys = [
        "esmc_cosine",
        "domain_jaccard",
        "domain_overlap",
        "seq_identity",
        "tm_score",
        "function_similarity",
    ]
    for key in tune_keys:
        if key not in best:
            continue
        local_best_val = best.get(key, 1.0)
        local_best_score = best_score
        for g in grid:
            trial = dict(best)
            trial[key] = g
            sc, _n = mean_obj(trial)
            if sc > local_best_score + 1e-9:
                local_best_score = sc
                local_best_val = g
        if local_best_val != best.get(key):
            best[key] = local_best_val
            best_score = local_best_score
            history.append(
                {
                    "step": f"tune:{key}",
                    "score": best_score,
                    "weights": {key: local_best_val},
                }
            )

    return {
        "status": "ok",
        "objective": "mean_loo_transfer_auprc_of_fused_donors",
        "n_held": len(held_to_hit_lists),
        "baseline_score": round(base_score, 6),
        "tuned_score": round(best_score, 6),
        "improvement": round(best_score - base_score, 6),
        "base_weights": weights,
        "tuned_weights": best,
        "history": history,
    }


def retune_label_thresholds(
    scored_labels: list[dict[str, Any]],
    *,
    base: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """
    Re-fit Strong/Likely/Unlikely thresholds on scores with binary y*.

    Each item: {p_hat: float, y: 0|1} where y is ground-truth binding.
    When y is unavailable, keep defaults (proposal §8).
    """
    base_thr = {"strong": 0.75, "likely": 0.50, "unlikely": 0.25, **(base or {})}
    pairs = [
        (float(x["p_hat"]), int(x["y"]))
        for x in scored_labels
        if x.get("p_hat") is not None and x.get("y") is not None
    ]
    if len(pairs) < 5:
        return {
            "status": "skipped",
            "reason": "need ≥5 labeled (p_hat, y) pairs",
            "thresholds": base_thr,
            "n": len(pairs),
        }

    # sweep likely threshold (binds if p >= likely); optimise Youden-like on binary
    best_t = float(base_thr["likely"])
    best_j = -1.0
    for t100 in range(20, 80, 2):
        t = t100 / 100.0
        tp = fp = tn = fn = 0
        for p, y in pairs:
            pred = 1 if p >= t else 0
            if pred == 1 and y == 1:
                tp += 1
            elif pred == 1 and y == 0:
                fp += 1
            elif pred == 0 and y == 0:
                tn += 1
            else:
                fn += 1
        sens = tp / (tp + fn) if (tp + fn) else 0.0
        spec = tn / (tn + fp) if (tn + fp) else 0.0
        j = sens + spec - 1.0
        if j > best_j:
            best_j = j
            best_t = t

    # keep ordering strong > likely > unlikely
    likely = best_t
    strong = min(0.95, max(likely + 0.15, float(base_thr["strong"])))
    unlikely = max(0.05, min(likely - 0.15, float(base_thr["unlikely"])))
    thr = {"strong": round(strong, 3), "likely": round(likely, 3), "unlikely": round(unlikely, 3)}
    return {
        "status": "ok",
        "thresholds": thr,
        "youden_j": round(best_j, 4),
        "n": len(pairs),
        "base": base_thr,
    }


# ---------------------------------------------------------------------------
# §7.4 Toolkit expansion proposals
# ---------------------------------------------------------------------------

def propose_toolkit_expansions(
    results: list[dict[str, Any]],
    *,
    attribution: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Cluster failure modes → human-reviewable tool proposals (proposal §7.4)."""
    proposals: list[dict[str, Any]] = []
    n_ood = 0
    n_no_donors = 0
    n_no_pred = 0
    n_struct_fail = 0
    n_emb_fail = 0

    for r in results:
        abstain = r.get("abstain") or {}
        if abstain.get("confident") is False:
            n_ood += 1
        donors = r.get("donors") or []
        if not donors and r.get("mode") == "transfer":
            n_no_donors += 1
        preds = r.get("predictions") or []
        if donors and not preds:
            n_no_pred += 1
        ret = r.get("retrieval") or {}
        if ret.get("struct_similarity_foldseek", {}).get("error") or ret.get(
            "structure_fetch", {}
        ).get("error"):
            n_struct_fail += 1
        if ret.get("esm_similarity", {}).get("error"):
            n_emb_fail += 1

    n = max(len(results), 1)
    if n_ood / n >= 0.3:
        proposals.append(
            {
                "id": "motif_or_rnacompete",
                "priority": "high",
                "failure_mode": "high_ood_rate",
                "fraction": round(n_ood / n, 3),
                "proposal": (
                    "Add RNAcompete / motif-similarity tool for remote homologs "
                    "when embedding OOD abstain fires."
                ),
                "human_review": True,
            }
        )
    if n_no_donors / n >= 0.2:
        proposals.append(
            {
                "id": "ppi_network",
                "priority": "medium",
                "failure_mode": "no_donors",
                "fraction": round(n_no_donors / n, 3),
                "proposal": (
                    "Add protein–protein interaction network neighbours as "
                    "fallback donor candidates when multi-view retrieval is empty."
                ),
                "human_review": True,
            }
        )
    if n_emb_fail / n >= 0.3:
        proposals.append(
            {
                "id": "embedding_env",
                "priority": "ops",
                "failure_mode": "esm_unavailable",
                "fraction": round(n_emb_fail / n, 3),
                "proposal": (
                    "Ops: ensure protein_embed conda + GPU; not a new scientific tool."
                ),
                "human_review": True,
            }
        )
    if n_struct_fail / n >= 0.3:
        proposals.append(
            {
                "id": "structure_cache",
                "priority": "medium",
                "failure_mode": "structure_fail",
                "fraction": round(n_struct_fail / n, 3),
                "proposal": (
                    "Pre-cache AF3/AFDB for catalogue; enlarge foldseek DB coverage."
                ),
                "human_review": True,
            }
        )
    if n_no_pred / n >= 0.2:
        proposals.append(
            {
                "id": "rhobind_env",
                "priority": "ops",
                "failure_mode": "predict_fail",
                "fraction": round(n_no_pred / n, 3),
                "proposal": "Ops: rhobind conda + checkpoints; donors had no predictions.",
                "human_review": True,
            }
        )

    attr = attribution or {}
    for t in attr.get("retirement_candidates") or []:
        proposals.append(
            {
                "id": f"retire_{t}",
                "priority": "low",
                "failure_mode": "low_attribution",
                "proposal": f"Consider demoting or retiring tool `{t}` after human review.",
                "human_review": True,
            }
        )

    if not proposals:
        proposals.append(
            {
                "id": "none",
                "priority": "info",
                "failure_mode": "none_dominant",
                "proposal": "No systematic failure cluster above thresholds.",
                "human_review": False,
            }
        )
    return proposals


# ---------------------------------------------------------------------------
# §7 orchestrator
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_evolved_config(
    *,
    tuned_weights: dict[str, float],
    thresholds: dict[str, float],
    path: Path = EVOLVED_CONFIG,
    base_path: Path = DEFAULT_CONFIG,
) -> Path:
    cfg = _load_yaml(base_path)
    cfg["fusion_weights"] = {**(cfg.get("fusion_weights") or {}), **tuned_weights}
    cfg["label_thresholds"] = {**(cfg.get("label_thresholds") or {}), **thresholds}
    cfg["schema_version"] = str(cfg.get("schema_version") or "2.0") + "+evolved"
    cfg["evolved"] = True
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    return path


def run_self_evolution(
    results: list[dict[str, Any]],
    *,
    held_to_hit_lists: Optional[dict[str, list[list[dict[str, Any]]]]] = None,
    scored_labels: Optional[list[dict[str, Any]]] = None,
    traces: Optional[list[dict[str, Any]]] = None,
    base_weights: Optional[dict[str, float]] = None,
    top_k: int = 5,
    write_config: bool = True,
) -> EvolutionReport:
    """
    Full offline self-evolution loop (proposal §7).

    Parameters
    ----------
    results
        Per-query agent/pipeline outputs (with retrieval, evidence_table, verdict).
    held_to_hit_lists
        For weight retune: held_rbp → list of hit lists (modalities).
        If None, built from results' retrieval when possible.
    scored_labels
        Optional [{p_hat, y}] for threshold calibration.
    traces
        Optional raw JSONL events for cache promotion.
    """
    report = EvolutionReport(n_val=len(results), n_traces=len(traces or []))

    # 1–2 attribution
    report.tool_attribution = tool_attribution(results)

    # 3 weights
    hmap = held_to_hit_lists
    if hmap is None:
        hmap = _hit_lists_from_results(results)
    if hmap:
        report.weight_retune = retune_weights(
            hmap, base_weights=base_weights, top_k=top_k
        )
    else:
        report.weight_retune = {
            "status": "skipped",
            "reason": "no held_to_hit_lists / retrieval hits",
        }
        report.notes.append("Weight retune skipped — provide LOO hit lists.")

    # 3 thresholds
    if scored_labels:
        report.threshold_retune = retune_label_thresholds(scored_labels)
    else:
        # soft labels from verdict p_hat if y unknown — skip
        report.threshold_retune = retune_label_thresholds([])

    # 4 toolkit
    report.toolkit_proposals = propose_toolkit_expansions(
        results, attribution=report.tool_attribution
    )

    # 5 cache promotion
    trace_rows = list(traces or [])
    # also synthesise from results
    for r in results:
        q = r.get("query") or {}
        trace_rows.append(
            {
                "type": "query_end",
                "uniprot": q.get("uniprot"),
                "alias": q.get("alias"),
                "donors": r.get("donors") or [],
                "verdict": r.get("verdict"),
            }
        )
    cache_data = promote_from_traces(trace_rows, promote_after=2)
    report.cache_promotion = {
        "stats": cache_data.get("stats"),
        "n_entries": len(cache_data.get("entries") or {}),
        "path": str(PACKAGE_ROOT / "rbp_eval" / "cache" / "proxy_map.json"),
    }

    # write evolved config
    if write_config and report.weight_retune.get("status") == "ok":
        thr = (report.threshold_retune or {}).get("thresholds") or {
            "strong": 0.75,
            "likely": 0.50,
            "unlikely": 0.25,
        }
        path = write_evolved_config(
            tuned_weights=report.weight_retune["tuned_weights"],
            thresholds=thr,
        )
        report.evolved_config_path = str(path)
        report.notes.append(f"Wrote evolved config → {path}")

    # persist report
    EVOLVED_REPORT.parent.mkdir(parents=True, exist_ok=True)
    EVOLVED_REPORT.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report.notes.append(f"Report → {EVOLVED_REPORT}")
    return report


def _hit_lists_from_results(
    results: list[dict[str, Any]],
) -> dict[str, list[list[dict[str, Any]]]]:
    """Best-effort: rebuild single-list hits from evidence_table for each alias target."""
    out: dict[str, list[list[dict[str, Any]]]] = {}
    for r in results:
        q = r.get("query") or {}
        held = q.get("alias") or q.get("query")
        if not held:
            continue
        et = r.get("evidence_table") or r.get("donors") or []
        hits = []
        for row in et:
            a = row.get("alias")
            if not a or a == held:
                continue
            hits.append(
                {
                    "alias": a,
                    "uniprot": row.get("uniprot") or "",
                    "score": float(row.get("fused_similarity") or row.get("score") or 0),
                    "metric": "fused",
                    "rank": len(hits) + 1,
                }
            )
        if hits:
            out[str(held)] = [hits]
    return out


def summarize_verdicts(results: list[dict[str, Any]]) -> dict[str, Any]:
    labels: dict[str, int] = {}
    for r in results:
        lab = (r.get("verdict") or {}).get("label") or "Unknown"
        labels[lab] = labels.get(lab, 0) + 1
    return {"n": len(results), "label_counts": labels}
