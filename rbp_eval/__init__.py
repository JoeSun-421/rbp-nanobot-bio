# -*- coding: utf-8 -*-
"""Evaluation package: traces, metrics, and self-evolution (``rbp_eval/``)."""

__all__ = [
    "EvolutionReport",
    "load_default_val_cases",
    "propose_toolkit_expansions",
    "retune_label_thresholds",
    "retune_weights",
    "run_batch",
    "run_loo_val_batch",
    "run_self_evolution",
    "tool_attribution",
]


def __getattr__(name: str):
    # Lazy imports so `python -m rbp_eval.runner` is clean
    if name in (
        "EvolutionReport",
        "propose_toolkit_expansions",
        "retune_label_thresholds",
        "retune_weights",
        "run_self_evolution",
        "tool_attribution",
    ):
        from rbp_eval import evaluator as _e

        return getattr(_e, name)
    if name in ("load_default_val_cases", "run_batch", "run_loo_val_batch"):
        from rbp_eval import runner as _r

        return getattr(_r, name)
    raise AttributeError(name)
