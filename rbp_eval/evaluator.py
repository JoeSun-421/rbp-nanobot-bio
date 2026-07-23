# -*- coding: utf-8 -*-
"""
Self-evolution evaluator (attribution, retune, toolkit proposals, cache).

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

from app.core.paths import (
    DEFAULT_EVOLVE_REPORT,
    PACKAGE_ROOT,
    PROXY_CACHE,
    ensure_artifact_dirs,
)

DEFAULT_CONFIG = PACKAGE_ROOT / "config" / "defaults.yaml"
EVOLVED_CONFIG = PACKAGE_ROOT / "config" / "evolved.yaml"
CANDIDATE_CONFIG = PACKAGE_ROOT / "config" / "evolved.candidate.yaml"
CANDIDATE_SEED = PACKAGE_ROOT / "config" / "evolved.candidate.yaml.example"
EVOLVED_REPORT = DEFAULT_EVOLVE_REPORT
ensure_artifact_dirs()


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
    abstain_retune: dict[str, Any] = field(default_factory=dict)
    toolkit_proposals: list[dict[str, Any]] = field(default_factory=list)
    cache_promotion: dict[str, Any] = field(default_factory=dict)
    evolved_config_path: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Tool attribution
# ---------------------------------------------------------------------------

def tool_attribution(
    results: list[dict[str, Any]],
    *,
    min_support_fraction: float = 0.05,
) -> dict[str, Any]:
    """
    Recover which evidence channels / tools supported correct (or any) verdicts.

    Uses:
      - supporting_rbps similarity/prob mass on successful (numeric p_hat) queries
      - evidence_table[].sim_by_modality keys
      - retrieval.* ok flags
    """
    modality_counts: dict[str, float] = {}
    tool_counts: dict[str, float] = {}
    support_tool_mass: dict[str, float] = {}
    n = 0
    n_with_support = 0
    n_success = 0

    # map modality → curated / delivery tool names
    modality_to_tool = {
        "esmc_cosine": "seq_similarity",
        "esm2_cosine": "seq_similarity",
        "saprot_cosine": "seq_similarity",
        "domain_jaccard": "domain_architecture",
        "domain_overlap": "domain_architecture",
        "seq_identity": "seq_similarity",
        "tm_score": "struct_similarity",
        "lddt": "struct_similarity",
        "fident": "struct_similarity",
        "function_similarity": "get_func_annotation",
        "rna_embed": "rna_similarity",
        "rna_fm": "rna_similarity",
        "fused": "fuse_similarity_views",
    }

    for r in results:
        n += 1
        et = r.get("evidence_table") or []
        ret = r.get("retrieval") or {}
        verdict = r.get("verdict") or {}
        supporting = verdict.get("supporting_rbps") or []
        p_hat = verdict.get("p_hat")
        success = p_hat is not None and not (
            r.get("mode") == "retrieval_only" and p_hat is None
        )
        # retrieval_only stubs never count as "success"
        if r.get("mode") == "retrieval_only":
            success = False
        else:
            try:
                success = p_hat is not None and float(p_hat) == float(p_hat)
            except (TypeError, ValueError):
                success = False
        if success:
            n_success += 1

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
                tname = modality_to_tool.get(str(mod))
                if tname and success:
                    support_tool_mass[tname] = support_tool_mass.get(tname, 0.0) + max(w, 0.0)

        # supporting_rbps quality mass
        if success and supporting:
            masses = []
            for s in supporting:
                if not isinstance(s, dict):
                    continue
                try:
                    sim = float(s.get("similarity_score") or 0.0)
                except (TypeError, ValueError):
                    sim = 0.0
                try:
                    prob = float(s.get("prob")) if s.get("prob") is not None else None
                except (TypeError, ValueError):
                    prob = None
                masses.append(max(sim, 0.0) * (prob if prob is not None else 1.0))
            total = sum(masses) or 1.0
            # attribute evenly across retrieval tools that succeeded this query
            active_tools = [
                t
                for t, meta in ret.items()
                if isinstance(meta, dict) and meta.get("ok")
            ]
            if not active_tools:
                active_tools = ["supporting_rbps"]
            share = (sum(masses) / total) / max(len(active_tools), 1)
            for t in active_tools:
                # normalize tool key names
                key = {
                    "domain": "domain_architecture",
                    "esm_similarity": "seq_similarity",
                    "struct_similarity_foldseek": "struct_similarity",
                }.get(t, t)
                support_tool_mass[key] = support_tool_mass.get(key, 0.0) + share

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

        # timeline tools from agent traces embedded in result
        for t in r.get("tools_used") or []:
            if isinstance(t, str):
                tool_counts[t] = tool_counts.get(t, 0.0) + 0.25

    # normalize
    mod_sum = sum(modality_counts.values()) or 1.0
    tool_sum = sum(tool_counts.values()) or 1.0
    support_sum = sum(support_tool_mass.values()) or 1.0
    mod_frac = {k: round(v / mod_sum, 4) for k, v in sorted(modality_counts.items())}
    tool_frac = {k: round(v / tool_sum, 4) for k, v in sorted(tool_counts.items())}
    support_frac = {
        k: round(v / support_sum, 4) for k, v in sorted(support_tool_mass.items())
    }

    # retirement candidates: tools registered in retrieval but low fraction
    retire_src = support_frac if support_frac else tool_frac
    retire = [
        t
        for t, f in retire_src.items()
        if f < min_support_fraction and t not in ("resolve_rbp", "lookup_proxy_cache")
    ]

    return {
        "n_results": n,
        "n_with_support": n_with_support,
        "n_success": n_success,
        "modality_mass": mod_frac,
        "tool_success_fraction": tool_frac,
        "supporting_evidence_fraction": support_frac,
        "retirement_candidates": retire,
        "note": (
            "Low-attribution tools are candidates for retirement or skill demotion; "
            "human review required before removing from registry. "
            "Never auto-edit delivery."
        ),
    }


# ---------------------------------------------------------------------------
# Weight & threshold re-tuning
# ---------------------------------------------------------------------------

def _load_loo_matrix() -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], float]]:
    import csv

    from app.backends.delivery.env import apply_delivery_env, resolve_delivery_paths

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
    transfer AUPRC of the fused donor policy.
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
    Minimises calibrated binary cross-entropy for the ``likely`` cut, with
    Youden's J as a secondary report. When y is unavailable, keep defaults.
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

    def _ce(t: float) -> float:
        # soft label via clipped probability around threshold (calibrated CE proxy)
        eps = 1e-6
        loss = 0.0
        for p, y in pairs:
            # map distance-to-threshold into a calibrated prob
            logit_scale = 8.0
            z = max(-20.0, min(20.0, logit_scale * (p - t)))
            # sigmoid
            pred = 1.0 / (1.0 + math.exp(-z))
            pred = min(1.0 - eps, max(eps, pred))
            loss += -(y * math.log(pred) + (1 - y) * math.log(1.0 - pred))
        return loss / len(pairs)

    def _youden(t: float) -> float:
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
        return sens + spec - 1.0

    best_t = float(base_thr["likely"])
    best_ce = _ce(best_t)
    best_j = _youden(best_t)
    for t100 in range(20, 80, 2):
        t = t100 / 100.0
        ce = _ce(t)
        j = _youden(t)
        # primary: minimise CE; tie-break: higher Youden
        if ce < best_ce - 1e-9 or (abs(ce - best_ce) < 1e-9 and j > best_j):
            best_ce = ce
            best_j = j
            best_t = t

    likely = best_t
    strong = min(0.95, max(likely + 0.15, float(base_thr["strong"])))
    unlikely = max(0.05, min(likely - 0.15, float(base_thr["unlikely"])))
    # keep ordering strong > likely > unlikely
    if strong <= likely:
        strong = min(0.95, likely + 0.15)
    if unlikely >= likely:
        unlikely = max(0.05, likely - 0.15)
    thr = {"strong": round(strong, 3), "likely": round(likely, 3), "unlikely": round(unlikely, 3)}
    return {
        "status": "ok",
        "objective": "calibrated_cross_entropy",
        "thresholds": thr,
        "ce": round(best_ce, 6),
        "youden_j": round(best_j, 4),
        "n": len(pairs),
        "base": base_thr,
    }


def retune_abstain_thresholds(
    held_to_hit_lists: dict[str, list[list[dict[str, Any]]]],
    *,
    base_thresholds: Optional[dict[str, float]] = None,
    weights: Optional[dict[str, float]] = None,
    top_k: int = 5,
    abstain_rate_band: tuple[float, float] = (0.05, 0.55),
    grid: Optional[list[float]] = None,
) -> dict[str, Any]:
    """Grid-search abstain thresholds on val LOO hit lists.

    Objective: maximise mean LOO transfer AUPRC among *non-abstained* held RBPs,
    while keeping the abstain rate inside ``abstain_rate_band``.
    """
    _, matrix = _load_loo_matrix()
    try:
        from app.core.runtime_config import abstain_thresholds as _ab

        live = dict(_ab())
    except Exception:
        live = {
            "esmc_cosine": 0.55,
            "esm2_cosine": 0.55,
            "domain_jaccard": 0.5,
            "domain_overlap": 0.5,
            "seq_identity": 0.30,
            "tm_score": 0.5,
            "fused": 0.45,
            "rna_embed": 0.40,
        }
    thr0 = {**live, **(base_thresholds or {})}
    wmap = {**DEFAULT_WEIGHTS, **(weights or {})}
    grid = grid or [0.25, 0.35, 0.45, 0.55, 0.65, 0.75]
    lo, hi = abstain_rate_band
    n_held = len(held_to_hit_lists)
    if n_held == 0:
        return {
            "status": "skipped",
            "reason": "no held_to_hit_lists",
            "thresholds": thr0,
        }

    def _eval(thr: dict[str, float]) -> tuple[float, float, int]:
        scores: list[float] = []
        n_abs = 0
        for held, lists in held_to_hit_lists.items():
            donors = fuse_rbp_hits(
                lists,
                weights=wmap,
                top_k=top_k,
                exclude_aliases={held},
                use_rank_normalize=True,
            )
            if not donors:
                n_abs += 1
                continue
            best = donors[0]
            metric = str(best.get("metric") or "fused")
            t = float(thr.get(metric, thr.get("fused", 0.45)))
            if float(best.get("score") or 0.0) < t:
                n_abs += 1
                continue
            vals = []
            for d in donors:
                a = matrix.get((held, d["alias"]))
                if a is not None:
                    vals.append(float(a))
            if not vals:
                # confident but no LOO cell — skip from mean, not abstain
                continue
            scores.append(sum(vals) / len(vals))
        rate = n_abs / n_held
        mean_s = sum(scores) / len(scores) if scores else 0.0
        return mean_s, rate, len(scores)

    base_mean, base_rate, base_n = _eval(thr0)
    best = dict(thr0)
    best_mean, best_rate, best_n = base_mean, base_rate, base_n
    history = [
        {
            "step": "init",
            "mean_transfer": round(base_mean, 6),
            "abstain_rate": round(base_rate, 4),
            "n_scored": base_n,
            "thresholds": dict(thr0),
        }
    ]

    def _in_band(rate: float) -> bool:
        return lo - 1e-9 <= rate <= hi + 1e-9

    def _better(mean_s: float, rate: float, cur_mean: float, cur_rate: float) -> bool:
        in_b = _in_band(rate)
        cur_in = _in_band(cur_rate)
        if in_b and not cur_in:
            return True
        if in_b == cur_in and mean_s > cur_mean + 1e-9:
            return True
        if in_b == cur_in and abs(mean_s - cur_mean) < 1e-9:
            # prefer rate closer to mid-band
            mid = 0.5 * (lo + hi)
            return abs(rate - mid) < abs(cur_rate - mid)
        return False

    tune_keys = ["fused", "esmc_cosine", "domain_jaccard", "domain_overlap", "rna_embed"]
    for key in tune_keys:
        if key not in best:
            best[key] = float(thr0.get(key, 0.45))
        local_val = best[key]
        local_mean, local_rate = best_mean, best_rate
        for g in grid:
            trial = dict(best)
            trial[key] = float(g)
            mean_s, rate, _n = _eval(trial)
            if _better(mean_s, rate, local_mean, local_rate):
                local_mean, local_rate, local_val = mean_s, rate, float(g)
        if abs(local_val - float(best.get(key, local_val))) > 1e-12:
            best[key] = local_val
            best_mean, best_rate, best_n = _eval(best)
            history.append(
                {
                    "step": f"tune:{key}",
                    "mean_transfer": round(best_mean, 6),
                    "abstain_rate": round(best_rate, 4),
                    "n_scored": best_n,
                    "thresholds": {key: local_val},
                }
            )

    return {
        "status": "ok",
        "objective": "mean_loo_transfer_among_non_abstained",
        "abstain_rate_band": [lo, hi],
        "n_held": n_held,
        "baseline": {
            "mean_transfer": round(base_mean, 6),
            "abstain_rate": round(base_rate, 4),
            "n_scored": base_n,
        },
        "tuned": {
            "mean_transfer": round(best_mean, 6),
            "abstain_rate": round(best_rate, 4),
            "n_scored": best_n,
        },
        "improvement": round(best_mean - base_mean, 6),
        "base_thresholds": thr0,
        "tuned_thresholds": best,
        "history": history,
    }


# ---------------------------------------------------------------------------
# Toolkit expansion proposals
# ---------------------------------------------------------------------------

def propose_toolkit_expansions(
    results: list[dict[str, Any]],
    *,
    attribution: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Cluster failure modes → human-reviewable toolkit proposals."""
    proposals: list[dict[str, Any]] = []
    n_ood = 0
    n_no_donors = 0
    n_no_pred = 0
    n_struct_fail = 0
    n_emb_fail = 0
    n_null_phat = 0
    failure_reasons: dict[str, int] = {}

    for r in results:
        abstain = r.get("abstain") or {}
        if abstain.get("confident") is False:
            n_ood += 1
        donors = r.get("donors") or []
        if not donors and r.get("mode") == "transfer":
            n_no_donors += 1
        preds = r.get("predictions") or []
        # retrieval_only stubs intentionally omit predictions
        if donors and not preds and r.get("mode") in ("transfer", "nanobot_llm"):
            n_no_pred += 1
        ret = r.get("retrieval") or {}
        if ret.get("struct_similarity_foldseek", {}).get("error") or ret.get(
            "structure_fetch", {}
        ).get("error"):
            n_struct_fail += 1
        if ret.get("esm_similarity", {}).get("error"):
            n_emb_fail += 1
        verdict = r.get("verdict") or {}
        if verdict.get("p_hat") is None and r.get("mode") != "retrieval_only":
            n_null_phat += 1
            expl = str(verdict.get("explanation") or "")
            reason = "p_hat_null"
            if "rc=-9" in expl or "OOM" in expl or "killed" in expl.lower():
                reason = "predict_oom_kill"
            elif "prior_missing" in expl or verdict.get("prior_missing"):
                reason = "prior_missing"
            elif "structure" in expl.lower() and "unavail" in expl.lower():
                reason = "structure_unavailable"
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

    n = max(len(results), 1)
    if n_null_phat / n >= 0.3:
        top_reason = max(failure_reasons, key=failure_reasons.get) if failure_reasons else "p_hat_null"
        proposals.append(
            {
                "id": "cluster_null_phat",
                "priority": "high",
                "failure_mode": top_reason,
                "fraction": round(n_null_phat / n, 3),
                "cluster_counts": failure_reasons,
                "proposal": (
                    "Systematic null p_hat cluster. If predict_oom_kill: raise cgroup RAM. "
                    "If prior_missing dominates: consider broader LOO coverage (delivery-side, "
                    "human-owned). Do not auto-edit delivery."
                ),
                "human_review": True,
            }
        )
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
# Self-evolution orchestrator
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
    path: Path = CANDIDATE_CONFIG,
    base_path: Path = DEFAULT_CONFIG,
    promoted: bool = False,
    abstain_thresholds: Optional[dict[str, float]] = None,
) -> Path:
    """Write evolved knobs. Default path is *candidate* (not live until promote)."""
    # Prefer existing target file so abstain_thresholds / axes survive retunes
    cfg = _load_yaml(path) if path.is_file() else {}
    if not cfg:
        # seed from live evolved or defaults
        cfg = _load_yaml(EVOLVED_CONFIG) if EVOLVED_CONFIG.is_file() else {}
    if not cfg:
        cfg = _load_yaml(base_path)
    # Always take fusion/label defaults as floor, then apply tuned values (incl. 0.0)
    base = _load_yaml(base_path)
    fw = {**(base.get("fusion_weights") or {}), **(cfg.get("fusion_weights") or {})}
    for k, v in (tuned_weights or {}).items():
        try:
            fw[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    cfg["fusion_weights"] = fw
    cfg["label_thresholds"] = {
        **(base.get("label_thresholds") or {}),
        **(cfg.get("label_thresholds") or {}),
        **(thresholds or {}),
    }
    ab = {
        **(base.get("abstain_thresholds") or {}),
        **(cfg.get("abstain_thresholds") or {}),
    }
    if abstain_thresholds:
        for k, v in abstain_thresholds.items():
            try:
                ab[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    if ab:
        cfg["abstain_thresholds"] = ab
    elif "abstain_thresholds" not in cfg and base.get("abstain_thresholds"):
        cfg["abstain_thresholds"] = dict(base["abstain_thresholds"])
    ver = str(cfg.get("schema_version") or base.get("schema_version") or "2.0")
    if not ver.endswith("+evolved"):
        ver = ver + "+evolved"
    cfg["schema_version"] = ver
    cfg["evolved"] = bool(promoted)
    cfg["candidate"] = not bool(promoted)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    return path


def promote_evolved_config(
    *,
    candidate: Path = CANDIDATE_CONFIG,
    live: Path = EVOLVED_CONFIG,
    require_reports: bool = True,
    seed: bool = False,
) -> Path:
    """Promote candidate → live evolved.yaml after light eval report asserts.

    Mirrors DSPy/Haystack: offline compile, then gate, then deploy policy.

    C6: when ``seed=True`` and the candidate file is missing (e.g. fresh clone —
    ``evolved.candidate.yaml`` is gitignored), copy the tracked seed
    ``evolved.candidate.yaml.example`` → candidate first so the promote link is
    reproducible without running the full ``evolve`` loop.
    """
    if not candidate.is_file():
        if seed and CANDIDATE_SEED.is_file():
            import shutil

            candidate.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CANDIDATE_SEED, candidate)
        else:
            raise FileNotFoundError(
                f"No candidate config at {candidate}. Run: rbp-agent evolve"
                + ("" if seed else "  (or `rbp-agent promote-evolved --seed` to bootstrap)")
            )
    if require_reports:
        from app.dev.gate import assert_eval_plan_report, assert_loo_report
        from app.core.paths import REPORTS

        loo = REPORTS / "eval_loo_report.json"
        plan = REPORTS / "evaluation_plan_report.json"
        if not loo.is_file() or not plan.is_file():
            raise FileNotFoundError(
                "Missing light eval reports. Run: rbp-agent gate   "
                f"(expected {loo.name} and {plan.name})"
            )
        assert_loo_report(loo)
        assert_eval_plan_report(plan)

    cfg = _load_yaml(candidate)
    cfg["evolved"] = True
    cfg["candidate"] = False
    live.parent.mkdir(parents=True, exist_ok=True)
    with open(live, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    try:
        from app.core.runtime_config import clear_runtime_config_cache

        clear_runtime_config_cache()
    except Exception:
        pass
    return live


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
    Full offline self-evolution loop.

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

    # base weights from runtime config when not supplied
    if base_weights is None:
        try:
            from app.core.runtime_config import fusion_weights

            base_weights = fusion_weights()
        except Exception:
            base_weights = None

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
        report.threshold_retune = retune_label_thresholds([])
        report.notes.append(
            "Threshold CE skipped — pass scored_labels / --with-labels for (p_hat,y) pairs."
        )

    # 3b abstain thresholds
    if hmap:
        tuned_w = None
        if report.weight_retune.get("status") == "ok":
            tuned_w = report.weight_retune.get("tuned_weights")
        report.abstain_retune = retune_abstain_thresholds(
            hmap, weights=tuned_w or base_weights, top_k=top_k
        )
    else:
        report.abstain_retune = {
            "status": "skipped",
            "reason": "no held_to_hit_lists / retrieval hits",
        }

    # 4 toolkit
    report.toolkit_proposals = propose_toolkit_expansions(
        results, attribution=report.tool_attribution
    )

    # 5 cache promotion
    trace_rows = list(traces or [])
    # also synthesise from results
    for r in results:
        q = r.get("query") or {}
        if isinstance(q, str):
            q = {"alias": q}
        alias = q.get("alias") or r.get("alias")
        uniprot = q.get("uniprot") or r.get("uniprot")
        trace_rows.append(
            {
                "type": "query_end",
                "query": q,
                "uniprot": uniprot,
                "alias": alias,
                "donors": r.get("donors") or [],
                "verdict": r.get("verdict"),
            }
        )
    cache_data = promote_from_traces(trace_rows, promote_after=2)
    report.cache_promotion = {
        "stats": cache_data.get("stats"),
        "n_entries": len(cache_data.get("entries") or {}),
        "path": str(PROXY_CACHE),
    }
    if results and results[0].get("axes_used_global") is not None:
        report.notes.append(f"axes_used={results[0].get('axes_used_global')}")

    # write evolved *candidate* config (promote separately after eval gate)
    can_write = (
        report.weight_retune.get("status") == "ok"
        or report.abstain_retune.get("status") == "ok"
    )
    if write_config and can_write:
        thr = (report.threshold_retune or {}).get("thresholds") or {
            "strong": 0.75,
            "likely": 0.50,
            "unlikely": 0.25,
        }
        tuned_w = (report.weight_retune or {}).get("tuned_weights") or (base_weights or {})
        abstain = (report.abstain_retune or {}).get("tuned_thresholds")
        path = write_evolved_config(
            tuned_weights=tuned_w,
            thresholds=thr,
            abstain_thresholds=abstain,
            path=CANDIDATE_CONFIG,
            promoted=False,
        )
        report.evolved_config_path = str(path)
        report.notes.append(
            f"Wrote candidate config → {path} (run: rbp-agent promote-evolved after gate)"
        )
        try:
            from app.core.runtime_config import clear_runtime_config_cache

            clear_runtime_config_cache()
        except Exception:
            pass

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
        if isinstance(q, str):
            held = q
        else:
            held = q.get("alias") or q.get("query")
        if not held:
            held = r.get("alias")
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
