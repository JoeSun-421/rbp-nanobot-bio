<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="460">
  <h1>nanobot-bio</h1>
  <p>An RNA–RBP interaction prediction agent built on Nanobot.<br/>
  Orchestrates <em>retrieve donors → borrow heads → integrate</em> and emits an auditable JSON verdict.</p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/stages-0%E2%86%921%E2%86%922%E2%86%923-green" alt="Stages">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
  <p><b>English</b> · <a href="README.zh.md">中文</a></p>
</div>

## 🧭 Navigation

- [Clone](#-clone-https)
- [Overview](#overview)
- [Features](#features)
- [Quick start](#-quick-start)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Control flow](#control-flow)
- [Configuration](#configuration)
- [Commands](#commands)
- [Scope](#scope-and-boundaries)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Docs](#docs)

---

## 📦 Clone (HTTPS)

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

Keep the delivery bundle as a **sibling** of this repo:

```text
bio_agent/
├── rbp-nanobot-bio/           ← this repository
└── rhobind_agent_delivery/    ← science bundle: registry, weights, DBs
```

Install, environment variables, data, and acceptance are documented in [`INSTALL.md`](INSTALL.md).

---

## Overview

`nanobot-bio` answers one question: *Does RNA R interact with RBP X?*

- Orchestration uses a **slim in-repo Nanobot** under `nanobot/`, Proposal §6.2: Agent Controller plus RBP toolkit. No Telegram, WebUI, or channels.
- Scientific scores come **only** from tools in `rhobind_agent_delivery`. This repo calls them through a read-only JSON bridge and never edits delivery sources, weights, or registry.
- Offline evaluation and self-evolution live in `rbp_eval/`, isolated from the chat path.
- The agent emits a JSON verdict with fields `label`, `confidence`, `p_hat`, `explanation`, and `supporting_rbps` for delivery acceptance.

---

## Features

### Agent loop

- **Stage 0→1→2→3** semantics with two LLM checkpoints: `commit_proxy_candidates` and `normalize_verdict`.
- **Three prediction paths**: in-catalogue own-head once then STOP; near-known fast path when identity ≥ 0.95; unseen retrieve → fuse → abstain → borrow heads → integrate.
- **Dual-axis sequence retrieval**: ESM-C embedding plus MMseqs — not protein BLASTn.
- **Structure axis**: AFDB first, AF3 fallback on by default. A probe failure surfaces a caveat and never writes similarity `0`.
- **Stage contract** enforced by `turn_guards`: fuse → commit → abstain → predict, data-driven via `stage_contract.py`.
- **JSON verdict schema** with a Stage-3 checklist: ≥2 failures force `confidence=low`.

### Toolkit — source of truth

- Tools are `nanobot.agent.tools.base.Tool` subclasses under `nanobot/agent/tools/rbp/`.
- Four views: sequence, structure, function, integrate.
- Delivery scripts run through `app/backends/delivery` as a JSON bridge with subprocess isolation and separate conda envs.
- `RBP_RAW_TOOLS=whitelist` is the curated default; `all` exposes the full 37-tool set for debugging; `none` disables raw tools.
- Optional phmmer remote-homology axis: set `RBP_PHMMER=1`.

### Offline evaluation & evolution

- `rbp_eval/` covers leave-one-RBP-out, ablations, and evolve-eval — never on the chat path.
- Self-evolution is **offline only**: `evolve-eval` writes a candidate; promote when `delta_auprc > 0` or HOLD; then land in `config/evolved.yaml`.
- `RBPTraceHook` writes `artifacts/traces/*.jsonl` for replay and attribution.

---

## ⚡ Quick start

```bash
bash scripts/setup_all.sh
# lighter: bash scripts/setup_all.sh --skip-af3
source .venv/bin/activate
nanobot-bio onboard && nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
# nanobot-bio chat
```

---

## Architecture

```text
User / Delivery acceptance
        │
        ▼
nanobot-bio CLI  →  Nanobot.run / run_streamed
        │
        ├─ nanobot/                 ← Controller + Toolkit SoT
        ├─ app/backends/delivery    ← read-only JSON bridge
        └─ rbp_eval/                ← offline Validation Evaluator
                │
                ▼
        rhobind_agent_delivery      ← Predictor + DBs + ready tools
```

| Layer | Path | Responsibility |
|-------|------|----------------|
| Agent Controller | in-repo `nanobot/` via `Nanobot.from_config` → `run` | Plan tools, two LLM checkpoints, emit JSON |
| Toolkit | `nanobot/agent/tools/rbp/` plus delivery scripts via bridge | Sequence / structure / function / integrate |
| Predictor | delivery `rhobind_predict` in conda env `rhobind` | Binding `prob` |
| Offline eval | `rbp_eval/` | LOO, ablations, evolve-eval — not chat |

---

## Repository layout

```text
nanobot-bio/
├── app/                 # Product shell: cli/{user,accept,eval,maint}, agent, delivery bridge
├── nanobot/             # Slim vendored framework + skills/rbp-agent + agent/tools/rbp
├── config/              # defaults.yaml Table 3 + evolved.yaml
├── rbp_eval/            # Offline evaluation / evolution
├── scripts/             # setup_all.sh, CI helpers
├── tests/               # pytest contract / compliance
├── docs/                # Proposal & checklists — local only, not on GitHub
├── workspace/           # Default Nanobot workspace, skill sync target
└── artifacts/           # Runtime reports / traces / cache — gitignored
```

---

## Control flow

| Path | Steps |
|------|-------|
| **In-catalogue — Stage 0** | `resolve_rbp` → `in_panel` → `predict_interaction` once → JSON → **STOP** |
| **Near-known** | `check_near_known` when identity ≥ 0.95 → headed donor once → JSON → **STOP** |
| **Unseen** | characterize → parallel retrieve `hits_emb`+`hits_seq` → `fuse_similarity_views` → `confidence_abstain` → `predict_interaction` on donors → integrate → JSON |

Defaults from Table 3 / `config/defaults.yaml`: `n_cand=5`, `tau_drop=0.30`, near-match `0.95`, label cuts `0.75 / 0.50 / 0.25`, cross-donor aggregate `weighted` per proposal §4 Σ s·p·c.

---

## Configuration

Defaults live in `config/defaults.yaml`: Table 3 knobs for `n_cand`, `tau_drop`, label thresholds, axes, fusion weights, abstain, llm, models. `config/evolved.yaml` is used only after offline gates pass and a candidate is promoted.

| Variable | Purpose |
|----------|---------|
| `BIO_ROOT` | Parent of `nanobot-bio` and delivery |
| `DELIVERY_ROOT` | Delivery package root `rhobind_agent_delivery` |
| `NANOBOT_SRC` | In-repo slim runtime — default `$NANOBOT_BIO_ROOT/nanobot` |
| `NANOBOT_BIO_ROOT` | This repo root |
| `NANOBOT_WORKSPACE` | Default `nanobot-bio/workspace` |
| `NANOBOT_CONFIG` | LLM config at `~/.nanobot/config.json` |
| `RBP_RAW_TOOLS` | `whitelist` / `all` / `none` |
| `NANOBOT_TOOL_ALLOW` | ToolLoader allowlist — default `rbp` |
| `RBP_PHMMER` | Set to `1` to enable the optional phmmer axis |
| `HF_HOME` / `HF_ENDPOINT` | ESM weights cache / mirror |
| `OMP_NUM_THREADS` | Thread cap for embedding tools |
| `AGENT_DB` / `RBP_REGISTRY` | Injected by delivery setup / app env |

LLM config: `nanobot-bio onboard` writes providers and API key into `~/.nanobot/config.json`. **Do not commit real API keys.**

---

## Commands

| Command | Audience | Purpose |
|---------|----------|---------|
| `nanobot-bio doctor` | All | Paths, registry, skill sync, axes / AF3 status |
| `nanobot-bio onboard` | User | LLM provider / API key |
| `nanobot-bio agent` / `chat` | User | Product runs via `Nanobot.run` / streamed |
| `nanobot-bio accept-golden` | Delivery | Own-head golden ≈0.966 on delivery pos RNA × PTBP1 |
| `nanobot-bio accept-llm` | Delivery | `nanobot_llm` mode + touchpoint evidence |
| `nanobot-bio gap-closure` | Delivery | Stage-0 / ordering fixture evidence pack |
| `nanobot-bio eval-plan` | Delivery / science | Ablation / metrics protocol |
| `nanobot-bio evolve` / `evolve-eval` | Science | Offline LOO batch + nested-split evolve |
| `nanobot-bio promote-evolved` | Science | Promote candidate config after gate |
| `nanobot-bio layout` / `gate` | CI | SoT layout + engineering gate |

Reports land under `artifacts/reports/`, or under `~/.nanobot-bio/artifacts/reports/` when overridden.

**Acceptance authority:** `nanobot-bio accept-golden` is the authoritative path for collaborators. It wraps and extends delivery-native smoke assertions. `rhobind_agent_delivery/agent/examples/run_example.sh` is delivery-only regression smoke with no app layer — use it only when debugging a single delivery tool.

### Chat slash commands

| Command | Purpose |
|---------|---------|
| `/help` | Show help |
| `/status` | Current model, tools, session |
| `/tools` | List registered tools |
| `/new` | Start a new session |
| `/clear` | Clear the screen |
| `/thinking` | Toggle thinking visibility |
| `/onboard` | Reconfigure LLM |
| `/quit` | Exit |

---

## Scope and boundaries

| In scope | Out of scope |
|----------|--------------|
| Agent CLI, skill, curated tools, delivery **bridge** | Editing `rhobind_agent_delivery/` sources, weights, registry |
| Offline eval / evolution in `rbp_eval/` | Online weight writes; inventing `p_hat` / `prob` |
| JSON verdict + Stage guards | Delivery v2 tools not in registry: calibration, motif, saliency, HDOCK |
| LLM planning + grounded explanation | Claiming calibrated P(bind) without a calibration tool and ECE evidence |

| Field | Meaning in this product |
|-------|-------------------------|
| `p_hat` | Score from predictor / `similarity_weighted_vote`, raw. Not a Delivery v2 calibrated probability. |
| `confidence` | Rules + Stage-3 checklist and related flags. Not calibrated P(bind). |
| `label` | `Strong` / `Likely` / `Unlikely` / `No` from Table-3 cuts on `p_hat` — defaults 0.75 / 0.50 / 0.25. |

---

## Testing

```bash
python -m pytest -q
```

Current baseline: `120 passed`.

Compliance gates:

```bash
pytest tests/test_proposal_compliance.py -q
pytest tests/test_stage_contract.py -q
pytest tests/test_section4_fidelity.py -q
```

---

## Troubleshooting

```bash
nanobot-bio doctor
```

| Symptom | Fix |
|---------|-----|
| Config missing | `nanobot-bio onboard` |
| `DELIVERY_ROOT` missing | Check sibling `rhobind_agent_delivery` or set the env |
| `NANOBOT_SRC` missing | Expect in-repo `nanobot-bio/nanobot/` |
| Skill out of sync | `python -m app.sync_overlay` or `nanobot-bio doctor` |
| `import nanobot` points at sibling / site-packages | Uninstall `nanobot-ai`, `pip install -e .`, put `NANOBOT_BIO_ROOT` first on `PYTHONPATH` |
| AF3 probe failed | See `.af3_status`; fall back to AFDB / sequence axis with a caveat |
| ESM killed / OOM `rc=-9` | Raise cgroup memory for `protein_embed`; set `HF_HOME` to local weights |
| LLM API key missing | `nanobot-bio onboard` |

---

## Docs

| Doc | Role |
|-----|------|
| [INSTALL.md](INSTALL.md) | Install / env / acceptance |
| [AGENTS.md](AGENTS.md) | Agent & CI constraints |
| [RELEASE.md](RELEASE.md) | How to cut a release |
| [CHANGELOG.md](CHANGELOG.md) | History — current tag **v0.5.1** |
| [VENDOR.md](VENDOR.md) | Slim-vendor maintainer notes |
| [README.zh.md](README.zh.md) | 中文 |

---

## Acknowledgements

Slim Agent Controller derived from [Nanobot](https://github.com/HKUDS/nanobot), vendored under `nanobot/` with channels and WebUI stripped. Scientific predictor and ready tools come from `rhobind_agent_delivery` through a read-only bridge. This repo does not modify delivery sources, weights, or registry.
