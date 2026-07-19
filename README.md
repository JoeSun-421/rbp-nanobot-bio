# nanobot-bio

[![Python](https://img.shields.io/badge/python-≥3.10-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-see%20repo-lightgrey.svg)](#license--attribution)
[![Release](https://img.shields.io/badge/release-v0.2.0-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

**English** | [中文](README.zh.md)

LLM agent for **RNA–RBP interaction** assessment. The product path is a real tool-using agent (`Nanobot.run` + skills + delivery bridge)—not a fixed pipeline.

> **Scope.** This repository is the **agent package only**. Scientific tools, checkpoints, and databases live in a sibling delivery bundle (`rhobind_agent_delivery/`, read-only at runtime) and are **not** redistributed here.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Behaviour & invariants](#behaviour--invariants)
- [Configuration](#configuration)
- [Releases](#releases)
- [Security](#security)
- [License & attribution](#license--attribution)

---

## Features

| Capability | Description |
|------------|-------------|
| Stage-0 own-head | In-catalogue RBPs → resolve → predict → structured JSON |
| Transfer path | Unseen RBPs → retrieve donors → predict → integrate |
| Multi-vendor LLM | OpenAI, Anthropic, DeepSeek, Gemini, Qwen, Zhipu, Moonshot, … |
| Science bridge | Conda-isolated delivery tools (ESM, Foldseek, RhoBind, AF3 optional) |
| Safe defaults | Never invents `p_hat`; no shell / web_search on the agent path |

---

## Architecture

```text
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────────┐
│  rbp-agent (CLI)    │────▶│  Nanobot runtime     │────▶│  rhobind_agent_delivery │
│  onboard / chat /   │     │  (sibling install)   │     │  (read-only science)    │
│  doctor / agent     │     │  + §6.2 RBP tools    │     │  conda envs + scripts   │
└─────────────────────┘     └──────────────────────┘     └─────────────────────────┘
```

| Path | When | Flow |
|------|------|------|
| Stage 0 | In-catalogue RBP | `resolve_rbp` → `predict_interaction` → JSON → **stop** |
| Transfer | Unseen / forced | retrieve → donor predict → integrate → JSON |

---

## Repository layout

This package keeps only the **proposal §6.2 overlay** under `nanobot/` (skills + `tools/rbp`). That directory is **source-of-truth for sync**, not an importable Python package. The full nanobot framework is a **sibling runtime**.

```text
nanobot-bio/                   # this git repository
├── nanobot/                   # §6.2 SoT — skills + agent/tools/rbp
├── backends/delivery/         # bridge to delivery scripts (conda envs)
├── core/                      # onboard / chat UX / verdict schema
├── rbp_eval/                  # traces & evaluation helpers
├── scripts/                   # setup_all, activate_env, sync helpers
├── cli.py                     # rbp-agent entry
└── integrate.py               # RBPAgent → Nanobot.from_config().run
```

Expected siblings (not in this git repo):

```text
<workspace>/
├── nanobot/                   ← runtime; `import nanobot` resolves here
├── nanobot-bio/               ← this package
└── rhobind_agent_delivery/    ← science bundle (set DELIVERY_ROOT)
```

Layout check:

```bash
python scripts/check_proposal_62_layout.py
```

---

## Requirements

- Python ≥ 3.10 (agent venv)
- Conda science envs from delivery: `protein_embed`, `rna`, `rhobind` (AF3 optional)
- **Recommended host:** CUDA GPU + sufficient RAM for RhoBind / ESM
- LLM API key via `rbp-agent onboard` (writes `~/.nanobot/config.json` locally—never commit it)
- Hugging Face weights for ESM (local cache; optional mirror via `HF_ENDPOINT`)

---

## Quick start

```bash
export BIO_ROOT=/path/to/workspace          # parent of nanobot-bio + delivery
export DELIVERY_ROOT=$BIO_ROOT/rhobind_agent_delivery

# First-time once: agent venv + science conda envs
bash $BIO_ROOT/nanobot-bio/scripts/setup_all.sh
# Agent-only (skip science conda): add --skip-conda

# Every session: light activate
source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh

rbp-agent onboard              # vendor + model + API key (local only)
rbp-agent onboard --list-models
rbp-agent doctor
rbp-agent chat
rbp-agent agent --example pos --strict
```

Override nanobot URL/path if needed: `NANOBOT_GIT`, `NANOBOT_SRC` (default `$BIO_ROOT/nanobot`).  
After a git pull, overlay re-sync: `ACTIVATE_HEAVY=1 source …/activate_env.sh`.

---

## CLI reference

| Command | Purpose |
|---------|---------|
| `rbp-agent onboard` | Configure LLM vendor + model + API key |
| `rbp-agent doctor` | Check delivery + conda envs |
| `rbp-agent chat` | Interactive agent session |
| `rbp-agent agent` | One-shot run (`--example`, `--message`, `--force-transfer`) |
| `rbp-agent own-head` | Golden own-head smoke (no LLM) |
| `rbp-agent predict` | Direct predict API wrapper |

```bash
# Own-head golden (no LLM)
rbp-agent own-head

# Same case via agent
rbp-agent agent --example pos --strict

# Force transfer path
rbp-agent agent --message "..." --force-transfer
```

---

## Behaviour & invariants

- Product path is **`Nanobot.run` only** (no fixed pipeline)
- **Never invent `p_hat`**. On predict OOM / timeout: `p_hat=null`, do not retry
- Stage 0 stops after a successful own-head predict
- Delivery under `rhobind_agent_delivery/` is **read-only**—bridge only
- Shell / `web_search` / `web_fetch` are disabled; use `literature_search` for papers

---

## Configuration

| Variable | Role |
|----------|------|
| `BIO_ROOT` | Workspace root (agent + delivery + sibling nanobot) |
| `DELIVERY_ROOT` | Path to `rhobind_agent_delivery` |
| `NANOBOT_SRC` | Sibling nanobot runtime |
| `NANOBOT_WORKSPACE` | Agent workspace (default: `nanobot-bio/workspace`) |
| `NANOBOT_CONFIG` | LLM config (default: `~/.nanobot/config.json`) |
| `RHOBIND_DEVICE` | `auto` / `cuda` / `cpu` |
| `CONDA_ENVS_PATH` | Optional conda envs directory if non-standard |
| `HF_HOME` / `HF_ENDPOINT` | HF cache + optional mirror |

Copy [`.env.example`](.env.example) → `.env` for local overrides (gitignored).

### LLM vendors

`rbp-agent onboard` writes nanobot config (`agents.defaults` + `providers.*`). Curated vendors include OpenAI, Anthropic, DeepSeek, Gemini, Qwen (DashScope), Zhipu, Moonshot, Mistral, MiniMax, OpenRouter, Groq, SiliconFlow, plus any OpenAI-compatible base URL.

---

## Releases

| Version | Notes |
|---------|--------|
| [v0.1.0](https://github.com/JoeSun-421/rbp-nanobot-bio/releases/tag/v0.1.0) | Initial agent package on GitHub |
| [v0.2.0](https://github.com/JoeSun-421/rbp-nanobot-bio/releases/tag/v0.2.0) | §6.2 overlay externalization, delivery client hardening, chat UX, tool fixes |

See [CHANGELOG.md](CHANGELOG.md).

---

## Security

- **Do not commit** API keys, `.env`, or `~/.nanobot/config.json`
- Rotate any key that was ever pasted into a chat or terminal history
- This repository excludes the delivery science bundle and large model weights by design

---

## License & attribution

Agent packaging and bridge code are part of this project. AlphaFold3 weights / RhoBind checkpoints shipped inside a delivery bundle are subject to their upstream licenses and must not be redistributed outside authorized use.

Nanobot runtime: [HKUDS/nanobot](https://github.com/HKUDS/nanobot).
