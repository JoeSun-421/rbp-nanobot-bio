# `app.backends.delivery`

**English** | [中文](README.zh.md)

Read-only bridge from the application to **`rhobind_agent_delivery`**. All RhoBind, ESM, Foldseek, AF3, registry, and LOO-prior calls pass through JSON tool envelopes executed in the appropriate conda environment.

## Purpose

Isolate scientific kernels (delivery) from the agent virtualenv, matching the subprocess / environment isolation patterns used by Nextflow processes, Snakemake conda directives, and Transformers pipeline backends.

## Responsibilities

1. Resolve `$DELIVERY_ROOT` and inject path environment variables.
2. Map logical tool names → scripts (`SCRIPT_MAP` / `mapping.yaml`).
3. Execute under the correct conda interpreter with env isolation.
4. Register curated Nanobot tools plus Stage whitelist raw tools.
5. Normalize payloads (e.g. inject evolved `abstain_thresholds` for `confidence_abstain`).

## Layout

| File | Role |
|------|------|
| `client.py` | `DeliveryToolClient`, `SCRIPT_MAP` |
| `env.py` | `apply_delivery_env`, path discovery |
| `registry.py` | Whitelist, tool builders, payload normalize |
| `stage_tools.py` | `STAGE_TOOL_SETS`, axis hard-gates |
| `mapping.yaml` | Human-readable map aligned with `SCRIPT_MAP` |
| `call_tool.py` / `examples.py` | Helpers |

## Constraints

- Do not modify delivery sources from this package.
- Prefer absolute conda Python binaries; keep agent site-packages off the child `PYTHONPATH` where required.
- Failures return structured envelopes; structure failure must not be coerced to similarity 0.

## Environment

| Variable | Role |
|----------|------|
| `DELIVERY_ROOT` | Bundle root |
| `AGENT_DB` / `TRANSFER_DIR` / … | Optional fine-grained overrides |
| `AF3_PYTHON` | AF3 interpreter after smoke |

## Related

[../../README.md](../../README.md) · [../](../README.md) · [../../../docs/工程指南.zh.md](../../../docs/工程指南.zh.md)
