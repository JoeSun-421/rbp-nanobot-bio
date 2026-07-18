#!/usr/bin/env python3
"""LOO eval + modality ablation (delivery agent/eval/README.md + DESIGN §5)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_VAL = [
    "NSUN2", "FXR2", "HNRNPUL1", "EEF2", "PTBP1",
    "CPSF6", "DHX30", "DDX51", "DROSHA", "RPS6",
]


def load_loo_summary(path: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["held_rbp"]] = r
    return rows


def load_transfer_matrix(path: Path) -> dict[tuple[str, str], float]:
    m = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m[(r["held_rbp"], r["foreign_rbp"])] = float(r["auprc"])
    return m


def _paths():
    from backends.delivery.env import apply_delivery_env, resolve_delivery_paths

    apply_delivery_env()
    paths = resolve_delivery_paths()
    summary = paths["agent_db"] / "transfer" / "loo_summary.csv"
    metrics = paths["agent_db"] / "transfer" / "loo_transfer_metrics.csv"
    if not summary.is_file():
        summary = paths["delivery_root"] / "agent" / "database" / "transfer" / "loo_summary.csv"
    if not metrics.is_file():
        metrics = paths["delivery_root"] / "agent" / "database" / "transfer" / "loo_transfer_metrics.csv"
    return summary, metrics


def policy_from_hits(
    held: str,
    hits: list[dict[str, Any]],
    matrix: dict[tuple[str, str], float],
    top_k: int,
) -> dict[str, Any]:
    from rbp_eval.fuse_hits import fuse_rbp_hits

    hits = [h for h in hits if h.get("alias") and h.get("alias") != held]
    donors = fuse_rbp_hits([hits], top_k=top_k, exclude_aliases={held})
    vals = []
    for d in donors:
        a = matrix.get((held, d["alias"]))
        if a is not None:
            vals.append(a)
    return {
        "donors": [d["alias"] for d in donors],
        "policy_best": max(vals) if vals else None,
        "policy_mean": (sum(vals) / len(vals)) if vals else None,
        "n_measured": len(vals),
    }


def main() -> int:
    from backends.delivery.client import DeliveryToolClient

    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--out", default="out/eval_loo_report.json")
    ap.add_argument("--ablation", action="store_true", help="Run modality ablation")
    args = ap.parse_args()

    summary_path, metrics_path = _paths()
    summary = load_loo_summary(summary_path)
    matrix = load_transfer_matrix(metrics_path)
    cli = DeliveryToolClient(offline=True, use_conda=False)

    modalities = {
        "domain": lambda held: cli.call(
            "domain_architecture", {"alias": held, "top_k": args.top_k * 2}
        ).get("hits")
        or [],
    }

    report_rows = []
    for held in DEFAULT_VAL:
        hits = modalities["domain"](held)
        pol = policy_from_hits(held, hits, matrix, args.top_k)
        sm = summary.get(held, {})
        own = float(sm["own_full_auprc"]) if sm.get("own_full_auprc") else None
        best_f = float(sm["best_foreign_auprc"]) if sm.get("best_foreign_auprc") else None
        mean_f = float(sm["mean_foreign_auprc"]) if sm.get("mean_foreign_auprc") else None
        report_rows.append(
            {
                "held_rbp": held,
                "modality": "domain",
                **pol,
                "own_full_auprc": own,
                "best_foreign_auprc": best_f,
                "mean_foreign_auprc": mean_f,
                "gap_to_own": None if pol["policy_best"] is None or own is None else own - pol["policy_best"],
                "gap_to_best_foreign": (
                    None
                    if pol["policy_best"] is None or best_f is None
                    else best_f - pol["policy_best"]
                ),
            }
        )

    ablation = {}
    if args.ablation:
        # domain-only is baseline; document that emb/seq need conda
        ablation["domain_only"] = {
            "mean_policy_best": _mean([r["policy_best"] for r in report_rows]),
            "mean_gap_to_best_foreign": _mean([r["gap_to_best_foreign"] for r in report_rows]),
            "note": "emb/seq/struct ablation requires protein_embed/rna envs — run on Linux with conda",
        }

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "protocol": "LOO light: hide head, select donors, lookup loo_transfer_metrics",
        "val_set": DEFAULT_VAL,
        "n": len(report_rows),
        "rows": report_rows,
        "ablation": ablation,
        "deficiencies": [
            "Does not re-run RhoBind on full test FASTA (needs rhobind env + disk panels)",
            "Donor selection domain-only offline; ESM-C axis not in light eval",
        ],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    for row in report_rows:
        print(
            f"{row['held_rbp']:12} policy_best={row['policy_best']} "
            f"best_foreign={row['best_foreign_auprc']} donors={row['donors'][:3]}"
        )
    return 0


def _mean(xs: list[Any]) -> Optional[float]:
    vals = [float(x) for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else None


if __name__ == "__main__":
    raise SystemExit(main())
