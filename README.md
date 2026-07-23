# nanobot-bio

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.3.0-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

**English** | [中文](README.zh.md)

Application layer for *in silico* RNA–RBP interaction assessment. CLI `nanobot-bio` (alias `rbp-agent`) orchestrates a read-only science toolkit (`rhobind_agent_delivery`) through [Nanobot](https://github.com/HKUDS/nanobot). Binding scores come **only** from predictor tools; the LLM plans tool calls and writes grounded explanations.

## Repository layout

```text
nanobot-bio/
  app/           # CLI, delivery bridge, chat UX, overlay sync
  plugin/        # Plugin SoT: skills/rbp-agent + agent/tools/rbp
  config/        # defaults.yaml / evolved.yaml
  rbp_eval/      # Offline LOO / eval-plan / evolve-eval / accept-llm
  scripts/       # setup / CI helpers
  tests/         # pytest
  docs/          # Local engineering notes (not required for install)
```

| Layer | Path | Role |
|-------|------|------|
| App | `app/` | `nanobot-bio` CLI, bridge, config load, sync into runtime |
| Plugin SoT | `plugin/nanobot/` | Skills + RBP tools (synced to `$NANOBOT_SRC`) |
| Eval | `rbp_eval/` | Offline validation / evolution (no online weight writes) |
| Science | `$DELIVERY_ROOT` | Read-only RhoBind / search DBs (not edited here) |
| Runtime | `$NANOBOT_SRC` | Nanobot agent loop (sibling install or clone) |

## What it does

- **In-catalogue (Stage 0):** `resolve_rbp` → own-head `predict_interaction` → JSON verdict → STOP
- **Near-known:** seq identity ≥ 95% → headed donor once → STOP
- **Unseen:** characterize → parallel retrieve → fuse → **abstain** → predict donors → integrate → JSON
- **Isolation:** heavy torch / mmseqs in conda subprocesses; agent stays light
- **Honesty:** no invented `p_hat`; structure failure ≠ similarity `0`; confidence is rules/checklist (not calibrated P(bind))

## Requirements

- Python ≥ 3.10
- Sibling Nanobot runtime (`$NANOBOT_SRC`) and `rhobind_agent_delivery` (`$DELIVERY_ROOT`)
- Optional: GPU + delivery conda envs (RhoBind / ESM / AF3)

## Install

```bash
cd nanobot-bio
bash scripts/setup_all.sh
source .venv/bin/activate
nanobot-bio onboard    # LLM provider / API key
nanobot-bio doctor
```

## Quick start

```bash
nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
nanobot-bio chat
```

## Commands

| Command | Audience | Purpose |
|---------|----------|---------|
| `doctor` / `onboard` | User | Paths, registry, skill sync, LLM config |
| `agent` / `chat` | User | Product Nanobot runs |
| `dev accept-golden` / `dev accept-llm` / `dev eval-plan` | Maintainer / Delivery | Acceptance & eval |
| `dev loo-heavy` / `dev evolve-eval` | Maintainer | Offline science loops |

## Configuration

Defaults: [`config/defaults.yaml`](config/defaults.yaml) (Table-3 thresholds, fusion weights, axes, `models:`). Use `config/evolved.yaml` only when `evolved: true` and gates pass.

## Delivery / Proposal notes

- Do **not** modify `rhobind_agent_delivery/` from this App.
- Product path is LLM agent (`Nanobot.run` / `run_streamed`), not a fixed Python DAG.
- `score_calibration` is Delivery **v2** (not in registry) — do not claim calibrated probabilities.
- Conflict ledger (local): `docs/冲突台账.zh.md`. Status: `docs/STATUS.md`.

## License / contact

Internal working package for the RBP agent delivery. See `CHANGELOG.md` for version history.
