# -*- coding: utf-8 -*-
"""
Proposal §6.2 — rbp_eval/runner.py

Batch-run validation queries, write JSONL traces (AgentHook-compatible),
feed the self-evolution evaluator.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from rbp_eval.hooks import JsonlTraceHook

DEFAULT_VAL_RBPS = [
    "NSUN2",
    "FXR2",
    "HNRNPUL1",
    "EEF2",
    "PTBP1",
    "CPSF6",
    "DHX30",
    "DDX51",
    "DROSHA",
    "RPS6",
]


def load_default_val_cases(
    *,
    rna: Optional[str] = None,
    force_transfer: bool = True,
) -> list[dict[str, Any]]:
    """Build D_val-style cases from delivery LOO hold-out list + sample RNA."""
    from backends.delivery.env import apply_delivery_env, delivery_root

    apply_delivery_env()
    ex = delivery_root() / "agent" / "examples"
    if rna is None:
        rna_path = ex / "sample_rna_pos.txt"
        rna = rna_path.read_text(encoding="utf-8").strip() if rna_path.is_file() else "AUGC" * 40

    cases = []
    for alias in DEFAULT_VAL_RBPS:
        cases.append(
            {
                "target_name": alias,
                "query": alias,
                "rna": rna,
                "force_transfer": force_transfer,
                "offline": True,
                "cohort": "K562",
            }
        )
    return cases


def run_batch(
    cases: Iterable[dict[str, Any]],
    *,
    trace_path: str | Path = "rbp_eval/traces/eval_run.jsonl",
    offline: bool = True,
    device: str = "auto",
    config: Optional[dict[str, Any]] = None,
    use_evolved_config: bool = True,
) -> list[dict[str, Any]]:
    """Removed with core.pipeline — product path is Nanobot.run only."""
    raise RuntimeError(
        "Fixed pipeline batch runner removed. "
        "Use: rbp-agent own-head | rbp-agent agent --example pos | "
        "rbp_eval.runner.run_loo_val_batch (retrieval-only for weight retune)."
    )


def run_loo_val_batch(
    *,
    top_k: int = 5,
    trace_path: str | Path = "rbp_eval/traces/loo_val.jsonl",
    offline: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, list[list[dict[str, Any]]]]]:
    """
    LOO-style val (retrieval-only): domain hits per held RBP for weight retune.
    Does **not** run a fixed pipeline; prediction stays on the Nanobot agent path.
    """
    from backends.delivery.client import DeliveryToolClient
    from backends.delivery.env import apply_delivery_env
    from core.verdict_schema import normalize_verdict

    apply_delivery_env()
    client = DeliveryToolClient(offline=offline, device="cpu", use_conda=False)
    cases = load_default_val_cases(force_transfer=True)
    held_hits: dict[str, list[list[dict[str, Any]]]] = {}
    tp = Path(trace_path)
    if not tp.is_absolute():
        tp = ROOT / tp
    hook = JsonlTraceHook(tp, session_key="rbp:eval")
    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        alias = case["query"]
        hook.push_event({"type": "query_start", "index": i, "case_keys": list(case.keys())})
        dom = client.call(
            "domain_architecture",
            {"alias": alias, "top_k": top_k * 2, "network": False},
        )
        hits = list(dom.get("hits") or [])
        held_hits[alias] = [hits]
        out = {
            "query": alias,
            "mode": "retrieval_only",
            "donors": hits[:top_k],
            "errors": [],
            "retrieval": {"domain": {"ok": bool(hits), "n": len(hits)}},
        }
        out["verdict"] = normalize_verdict(
            {
                "label": "No",
                "p_hat": None,
                "confidence": "low",
                "explanation": (
                    f"Retrieval-only LOO stub for {alias} "
                    f"(n_domain_hits={len(hits)}); score via Nanobot agent."
                ),
                "supporting_rbps": [
                    {"alias": h.get("alias"), "similarity_score": h.get("score")}
                    for h in hits[:top_k]
                ],
            }
        )
        hook.push_event(
            {
                "type": "query_end",
                "index": i,
                "query": alias,
                "mode": out["mode"],
                "donors": out["donors"],
                "verdict": out["verdict"],
                "errors": out["errors"],
            }
        )
        results.append(out)
    return results, held_hits


def load_traces(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: python -m rbp_eval.runner [--evolve]"""
    import argparse

    from rbp_eval.evaluator import run_self_evolution, summarize_verdicts

    ap = argparse.ArgumentParser(description="Batch val runner + optional self-evolution")
    ap.add_argument("--evolve", action="store_true", help="Run §7 self-evolution after batch")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument(
        "--trace",
        default="rbp_eval/traces/loo_val.jsonl",
        help="JSONL trace path",
    )
    ap.add_argument("--out", default="out/val_batch_results.json")
    args = ap.parse_args(argv)

    results, held_hits = run_loo_val_batch(top_k=args.top_k, trace_path=args.trace)
    summary = summarize_verdicts(results)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {"summary": summary, "n": len(results), "results": results},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("summary:", json.dumps(summary, ensure_ascii=False))
    print("wrote", out_path)

    if args.evolve:
        traces = load_traces(args.trace)
        report = run_self_evolution(
            results,
            held_to_hit_lists=held_hits,
            traces=traces,
            top_k=args.top_k,
            write_config=True,
        )
        print("self-evolution:", json.dumps(report.to_dict(), indent=2, ensure_ascii=False)[:2000])
        print("evolved_config:", report.evolved_config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
