# nanobot-bio

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.3.0-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

**English** | [中文](README.zh.md)

Application layer for *in silico* RNA–RBP interaction assessment. The `rbp-agent` CLI drives a [Nanobot](https://github.com/HKUDS/nanobot) agent that calls a read-only science toolkit (`rhobind_agent_delivery`). Binding scores come only from predictor tools; the LLM plans tool use and writes grounded explanations.

## Features

- **In-catalogue (Stage 0):** resolve RBP → own-head `predict_interaction` → JSON verdict
- **Transfer path:** multi-view retrieval (sequence / structure / function) → donor heads → integrate
- **Isolated science backends:** conda-backed RhoBind, ESM, Foldseek; optional AF3; agent-local RNA similarity
- **Evaluation:** light LOO lookup, evaluation-plan ablations, nested-split evolve-eval
- **Safety defaults:** no shell / generic web tools; `p_hat=null` on OOM without inventing scores

## Architecture

```text
rbp-agent (App)  →  Nanobot runtime ($NANOBOT_SRC)  →  delivery ($DELIVERY_ROOT, read-only)
     │                      │
     ├─ config/             ├─ synced tools from nanobot/agent/tools/rbp/
     ├─ rbp_eval/           └─ skill from nanobot/skills/rbp-agent/
     └─ artifacts/
```

| Layer | Role |
|-------|------|
| App | CLI, bridge, config, acceptance, SoT sync |
| Runtime | Agent loop, tool registry, sessions |
| Science | Stateless predictors and databases (not modified by this repo) |

## Requirements

- Python ≥ 3.10
- Sibling checkouts: Nanobot runtime and `rhobind_agent_delivery` (typical layout under a shared `BIO_ROOT`)
- Optional: GPU + conda envs from delivery setup for RhoBind / ESM / AF3

## Install

```bash
cd nanobot-bio
bash scripts/setup_all.sh
source .venv/bin/activate
```

Configure an LLM provider (OpenAI-compatible):

```bash
rbp-agent onboard
# or: bash ../scripts/configure_llm.sh --ping
```

## Quick start

```bash
rbp-agent doctor
rbp-agent mvp
rbp-agent agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
rbp-agent chat
```

## CLI

| Command | Purpose |
|---------|---------|
| `doctor` | Paths, registry, skill sync, model capability matrix |
| `onboard` | LLM provider / API key / model |
| `mvp` / `own-head` | Acceptance paths |
| `agent` / `chat` | Product Nanobot runs |
| `eval-plan` / `evolve` / `evolve-eval` | Offline evaluation and strategy candidates |
| `layout` / `gate` / `compliance` | Engineering checks |

## Configuration

Defaults live in [`config/defaults.yaml`](config/defaults.yaml) (thresholds, fusion weights, `models:` metadata). Live evolved overlays use `config/evolved.yaml` only when `evolved: true` after a passing gate.

## Evaluation

- Light LOO uses delivery transfer CSVs (not full RhoBind recompute on all FASTAs).
- Promote evolved configs only with engineering gate **and** nested-split evidence (`delta_auprc > 0`); otherwise keep candidates.

## Limitations

- AF3 may be unavailable on some GPUs; AFDB → Foldseek remains the default structure path.
- Default RNA similarity is a mock embedder; fusion weights for `rna_*` stay at 0 until a real checkpoint is configured.
- Label-threshold calibration needs an external `{p_hat, y}` set.

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/工程指南.zh.md](docs/工程指南.zh.md) | Contracts, E2E, AF3, change gates (§9) |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |

## Citation

Cite the delivery scientific methods (RhoBind LOO / DESIGN), the Nanobot runtime, and this application version (e.g. v0.3.0) as appropriate.

## Security

Do not commit API keys, `.env`, or `~/.nanobot/config.json`. Rotate credentials that appear in logs.

## License

Application packaging and bridge code are part of this project. Delivery weights and checkpoints follow upstream licenses. Runtime: [HKUDS/nanobot](https://github.com/HKUDS/nanobot).
