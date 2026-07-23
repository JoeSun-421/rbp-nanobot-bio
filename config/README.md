# `config/`

**English** | [中文](README.zh.md)

Runtime YAML for fusion weights, abstain thresholds, label thresholds, integrate/predict policies, and structure axes. Loaded by `app.core.runtime_config` and related tools.

## Files

| File | Role | Writer |
|------|------|--------|
| `defaults.yaml` | Baseline knobs | Human / release |
| `evolved.candidate.yaml` | Offline evolve output (`candidate: true`) | `rbp-agent evolve` |
| `evolved.yaml` | Live knobs (`evolved: true`) | `rbp-agent promote-evolved` |

## Semantics

- Live merge occurs only when `evolved: true` (DSPy-style compile then deploy).
- Explicit `0.0` fusion weights disable modalities; they must not fall back to defaults.
- Abstain thresholds are injected into `confidence_abstain` unless the caller overrides them.

## Related

[../README.md](../README.md) · [../app/core/](../app/core/README.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md) §4.5
