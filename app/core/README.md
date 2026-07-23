# `app.core`

**English** | [中文](README.zh.md)

Shared application utilities: artifact paths, LLM onboarding, terminal UX, runtime configuration merge, and verdict JSON schema.

## Modules

| Module | Role |
|--------|------|
| `paths.py` | Canonical `artifacts/{traces,sessions,reports,cache,logs,diag}`; session symlink |
| `onboard.py` | Multi-vendor LLM config → `~/.nanobot/config.json` |
| `chat_ux.py` | Terminal presentation (thinking fold, prompts, resource hints) |
| `runtime_config.py` | Merge `defaults.yaml` + live `evolved.yaml` when `evolved: true` |
| `verdict_schema.py` | Validate / normalize final agent JSON |

## Design notes

Path conventions follow scientific project practice of a single writable outputs root (cf. Nextflow `work`/publishDir, Snakemake results dirs, Hugging Face `cache_dir`), keeping code trees free of run products.

## Related

[../README.md](../README.md) · [../../config/](../../config/README.md) · [../../docs/工程指南.zh.md](../../docs/工程指南.zh.md)
