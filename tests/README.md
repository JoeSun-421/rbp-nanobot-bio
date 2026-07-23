# `tests/`

**English** | [中文](README.zh.md)

Pytest suite for imports, mapping consistency, onboard/device helpers, own-head path logic, verdict unwrapping, layout compliance, evaluation metrics, self-evolution helpers, RNA similarity mocks, and chat UX. Heavy GPU delivery jobs are not required by default (cf. Transformers / PyTorch unit vs integration split).

## Run

```bash
source .venv/bin/activate
pytest -q
# or
rbp-agent gate --skip-eval
```

Coverage fail-under is configured in `pyproject.toml` (30%).

## Suite map (representative)

| Test module | Focus |
|-------------|--------|
| `test_skeleton_imports.py` | Import smoke |
| `test_mapping_sync.py` | `mapping.yaml` ↔ whitelist / proposal tools |
| `test_device_and_onboard.py` | Device helpers / onboard |
| `test_own_head_path.py` | Stage-0 logic |
| `test_verdict_unwrap.py` | Verdict schema |
| `test_evaluation_plan_metrics.py` | AUROC / AUPRC / ECE helpers |
| `test_self_evolution.py` | Fuse, cache, retune, evolve report |
| `test_evolve_eval.py` | Nested-split evolve-eval schema |
| `test_rna_similarity.py` | Mock RNA bank / tool registration |
| `test_gate_report_schema.py` | LOO / eval-plan assert helpers |
| `test_chat_ux.py` | Terminal UX |

## Host-level acceptance

Use `rbp-agent layout|doctor|own-head|mvp` for machine-level checks: [../docs/工程指南.zh.md](../docs/工程指南.zh.md) §6.

## Related

[../README.md](../README.md) · [../app/acceptance/](../app/acceptance/README.md)
