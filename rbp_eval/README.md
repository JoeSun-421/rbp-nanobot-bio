# `rbp_eval`

**English** | [中文](README.zh.md)

Evaluation and offline self-evolution package for **nanobot-bio**. Implements light leave-one-out (LOO) transfer lookup, evaluation-plan ablations, multi-view fusion helpers, proxy-cache promotion, Nanobot trace hooks, and nested-split evolve evaluation.

## Purpose

Quantify retrieval–transfer policies without modifying delivery. Light protocols follow the evaluation style of scientific toolkits that separate *protocol harnesses* from *model kernels* (cf. Scanpy metrics modules, Transformers `evaluate`, DSPy offline compile loops).

## Modules

| Module | Role |
|--------|------|
| `loo_eval.py` | Light LOO → `artifacts/reports/eval_loo_report.*` |
| `evaluation_plan.py` | Held-out split, AUROC/AUPRC, ablations, strata, faithfulness sheet |
| `evolve_eval.py` | Train/test medoid split; defaults vs retuned on held-out half |
| `runner.py` | Val batch hit lists for evolve |
| `evaluator.py` | Attribution, weight/abstain/label retune, toolkit proposals, cache promote |
| `fuse_hits.py` | Multi-view fusion |
| `proxy_cache.py` | `artifacts/cache/proxy_map.json` |
| `nanobot_hooks.py` / `hooks.py` / `trace_schema.py` | Structured traces |

## Entrypoints

```bash
rbp-agent eval-plan
rbp-agent evolve [--with-esm] [--with-labels PATH]
rbp-agent evolve-eval [--tier-a-ok true]
python -m rbp_eval.loo_eval
python -m rbp_eval.evaluation_plan
python -m rbp_eval.evolve_eval
```

## Outputs

| Artifact | Content |
|----------|---------|
| `eval_loo_report.*` | Policy vs own-head transfer summaries |
| `evaluation_plan_report.*` | Ablations, strata, primary metrics |
| `evolve_eval_report.*` | Nested-split `delta_auprc`, promote suggestion |
| `self_evolution_report.json` | Full evolve report |
| `proxy_map.json` | Promoted Stage-1 bypass entries |

## Limitations

- Light LOO uses CSV lookup; full FASTA force-transfer recompute is deferred.
- Label CE retune requires `{p_hat, y}` pairs.
- Nested split reduces but does not eliminate optimism from shared transfer matrices.

## Related

[../README.md](../README.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md) §4.5–§6 · [../app/](../app/README.md)
