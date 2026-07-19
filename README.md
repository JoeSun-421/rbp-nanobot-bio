# nanobot-bio

**English** | [中文](README.zh.md)

LLM agent for **RNA–RBP interaction** assessment. Product path is a true tool-using agent (`Nanobot.run` + skills + delivery bridge)—not a fixed pipeline.

This repository is the **agent package** only. Scientific tools, checkpoints, and databases live in a sibling delivery bundle (`rhobind_agent_delivery/`, read-only at runtime).

---

## What it does

Given a protein (name / UniProt / sequence) and optional RNA context, the agent:

1. Resolves whether the RBP is in the catalogue (**Stage 0**)
2. Runs own-head prediction, **or** retrieves similar donors and transfers
3. Returns a structured verdict (`label`, `p_hat`, `confidence`, evidence)—never invents scores

| Path | When | Flow |
|------|------|------|
| Stage 0 | In-catalogue RBP | `resolve_rbp` → `predict_interaction` → JSON → **stop** |
| Transfer | Unseen / forced | retrieve → donor predict → integrate → JSON |

---

## Repository layout

This package keeps only the **proposal §6.2 overlay** under `nanobot/` (skills + `tools/rbp`). That directory is **source-of-truth for sync**, not an importable Python package (no top-level `__init__.py`). The full nanobot framework is a **sibling runtime** (`pip install -e $BIO_ROOT/nanobot`). `activate_env.sh` syncs the overlay into that runtime.

```text
nanobot-bio/                   # this git repo
  nanobot/                     # §6.2 SoT only — NOT a full framework
    skills/rbp-agent/SKILL.md
    agent/tools/rbp/*.py
  backends/delivery/           # bridge to delivery scripts (conda envs)
  core/                        # onboard / chat UX / verdict schema
  rbp_eval/                    # traces & self-evolution helpers
  cli.py                       # rbp-agent entry
  integrate.py                 # RBPAgent → Nanobot.from_config().run
  scripts/activate_env.sh      # env bootstrap + overlay sync
```

Expected siblings (not in this git repo):

```text
bio_agent/
  nanobot/                     ← runtime; import nanobot → here
  nanobot-bio/                 ← this package
  rhobind_agent_delivery/      ← science bundle (set DELIVERY_ROOT)
```

Layout check:

```bash
python scripts/check_proposal_62_layout.py
```

---

## Requirements

- Python ≥ 3.10 (package venv)
- Conda science envs from delivery: `protein_embed`, `rna`, `rhobind` (AF3 optional)
- **Ideal science host:** CUDA GPU + ≥ 8–16 GiB RAM (HANDOFF `device=cuda`). Tools default to `auto` → CUDA when available
- LLM: pick any supported vendor/model via `rbp-agent onboard` (writes `~/.nanobot/config.json` for `Nanobot.from_config`)
- Hugging Face weights for ESM (local cache / mirror). `activate_env.sh` sets `HF_HOME` and `HF_ENDPOINT`

---

## Quick start

```bash
export BIO_ROOT=/path/to/bio_agent          # parent of nanobot-bio + delivery
export DELIVERY_ROOT=$BIO_ROOT/rhobind_agent_delivery

source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh
# installs sibling nanobot + this package, syncs §6.2 tools/skill

rbp-agent onboard              # pick vendor + model + API key
rbp-agent onboard --list-models
rbp-agent doctor               # health check
rbp-agent chat                 # Nanobot.run interactive agent
# science tools use --device auto (cuda if present):
rbp-agent agent --example pos --strict
```
Create science envs once (from delivery):

```bash
bash $DELIVERY_ROOT/agent/setup_envs.sh
# or selectively: protein_embed / rna / rhobind / af3
```

---

## CLI

| Command | Purpose |
|---------|---------|
| `rbp-agent onboard` | Pick LLM vendor + model + API key |
| `rbp-agent doctor` | Check delivery + conda envs |
| `rbp-agent chat` | Interactive agent session |
| `rbp-agent agent` | One-shot agent run (`--example`, `--message`, `--force-transfer`) |
| `rbp-agent own-head` | Golden own-head smoke (no LLM) |
| `rbp-agent predict` | Direct predict API wrapper |

```bash
# Own-head golden (no LLM) — expect p_hat ≈ 0.966
rbp-agent own-head

# Same case via agent
rbp-agent agent --example pos --strict

# Force transfer path
rbp-agent agent --message "..." --force-transfer
```

---

## Behaviour & invariants

- Product path is **`Nanobot.run` only** (no fixed `core/pipeline`)
- **Never invent `p_hat`**. On predict OOM / timeout: `p_hat=null`, do not retry
- Stage 0 must stop after a successful own-head predict
- Delivery code under `rhobind_agent_delivery/` is **read-only**—bridge only
- Do not commit API keys or `.env` with secrets

---

## Acceptance

Scientific goldens are defined by the delivery bundle (own-head ≈ **0.966**, AUPRC 0.9311). When delivery docs are present locally:

```bash
# Delivery factory smoke (no nanobot)
bash $DELIVERY_ROOT/agent/examples/run_example.sh cpu
```

See delivery `agent/examples/README.md` for expected step-by-step output.

---

## Configuration

| Variable | Role |
|----------|------|
| `BIO_ROOT` | Workspace root containing agent + delivery + sibling nanobot |
| `DELIVERY_ROOT` | Path to `rhobind_agent_delivery` |
| `NANOBOT_SRC` | Sibling nanobot runtime (default: `$BIO_ROOT/nanobot`) |
| `NANOBOT_WORKSPACE` | Agent workspace (default: `nanobot-bio/workspace`) |
| `NANOBOT_CONFIG` | LLM config (default: `~/.nanobot/config.json`) |
| `RHOBIND_DEVICE` | `auto` (default) / `cuda` / `cpu` — science tool device |
| `HF_HOME` / `HF_ENDPOINT` | Local HF cache + mirror (set by `activate_env.sh`) |

### LLM vendors

`rbp-agent onboard` writes nanobot’s config (`agents.defaults.provider/model` + `providers.*`). Supported curated vendors include OpenAI, Anthropic, DeepSeek, Gemini, Qwen (DashScope), Zhipu, Moonshot, Mistral, MiniMax, OpenRouter, Groq, SiliconFlow, plus any OpenAI-compatible custom base URL. List models with `rbp-agent onboard --list-models`.

Copy [`.env.example`](.env.example) to `.env` for local overrides (gitignored).

---

## License & attribution

Agent packaging and bridge code are part of this project. AlphaFold3 weights / RhoBind checkpoints shipped inside a delivery bundle are subject to their upstream licenses and must not be redistributed outside authorized use.
