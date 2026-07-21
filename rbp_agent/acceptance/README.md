# `rbp_agent.acceptance`

**English** | [中文](README.zh.md)

Acceptance and compliance checks invoked by `rbp-agent` subcommands. These modules replace ad-hoc shell-only gates with importable, testable entrypoints (cf. pytest suites and CI jobs in Transformers / Lightning / ruff repositories).

## Module ↔ CLI

| Module | CLI | Checks |
|--------|-----|--------|
| `layout.py` | `layout` | Overlay paths; `import nanobot` → Runtime |
| `gate.py` | `gate` | ruff + pytest + layout; optional light LOO / eval-plan |
| `own_head.py` | `own-head` | PTBP1 golden ≈ 0.966 (no LLM) |
| `mvp.py` | `mvp` | End-to-end `Nanobot.run` path |
| `compliance.py` | `compliance` | Delivery paths / SCRIPT_MAP → `compliance_report.json` |

## Recommended order

On a new host: **layout → doctor → own-head → mvp**. Full protocol: [../../docs/工程指南.zh.md](../../docs/工程指南.zh.md) §6.

## Related

[../README.md](../README.md) · [../../tests/](../../tests/README.md)
