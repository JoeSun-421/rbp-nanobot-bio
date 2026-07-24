<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="460">
  <h1>nanobot-bio</h1>
  <p>An RNA–RBP interaction prediction agent built on Nanobot. It orchestrates <em>retrieve donors → borrow heads → integrate</em> and emits an auditable JSON verdict.</p>
  <p>
    <a href="#quick-start">Quick start</a> ·
    <a href="#architecture">Architecture</a> ·
    <a href="#configuration">Configuration</a> ·
    <a href="#commands">Commands</a> ·
    <a href="#testing">Testing</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/stages-0%E2%86%921%E2%86%922%E2%86%923-green" alt="Stages">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
  <p><b>English</b> | <a href="README.zh.md">中文</a></p>
</div>

## What this is

`nanobot-bio` answers one question: *Does RNA R interact with RBP X?*

It is a **scientific agent application**, not a personal assistant:

- Orchestration uses a **slim in-repo Nanobot** under `nanobot/` (Proposal §6.2): Agent Controller + RBP toolkit, without Telegram/WebUI/channels.
- Scientific scores are produced **only** by tools in `rhobind_agent_delivery`. This repo calls them through a read-only JSON bridge and never edits delivery sources, weights, or registry.
- Offline evaluation and self-evolution live in `rbp_eval/`, isolated from the chat path.
- The agent emits a JSON verdict (`label`, `confidence`, `p_hat`, `explanation`, `supporting_rbps`) for delivery acceptance.


## Features

### Agent loop

- **Stage 0→1→2→3** semantics with two LLM checkpoints (`commit_proxy_candidates`, `normalize_verdict`).
- **Three prediction paths**: in-catalogue (own-head once, then STOP), near-known (identity ≥ 0.95 fast path), unseen (retrieve → fuse → abstain → borrow heads → integrate).
- **Dual-axis sequence retrieval**: ESM-C embedding + MMseqs (not protein BLASTn).
- **Structure axis**: AFDB first, AF3 fallback on by default; a probe failure surfaces a caveat, never similarity `0`.
- **Stage contract** enforced by `turn_guards`: fuse → commit → abstain → predict ordering is data-driven (`stage_contract.py`).
- **JSON verdict schema** with a Stage-3 checklist (≥2 failures force `confidence=low`).

### Toolkit (source of truth)

- Tools are `nanobot.agent.tools.base.Tool` subclasses under `nanobot/agent/tools/rbp/`.
- Four views: sequence / structure / function / integrate.
- Delivery scripts are invoked through `app/backends/delivery` as a JSON bridge (subprocess isolation, separate conda envs).
- `RBP_RAW_TOOLS=whitelist` (curated default) / `all` (full 37-tool set, for debugging) / `none`.
- Optional phmmer remote-homology axis via `RBP_PHMMER=1`.

### Offline evaluation & evolution

- `rbp_eval/`: leave-one-RBP-out, ablations, evolve-eval — never on the chat path.
- Self-evolution is **offline only**: `evolve-eval` produces a candidate → `delta_auprc > 0` or HOLD gate → promote to `config/evolved.yaml`.
- `RBPTraceHook` writes `artifacts/traces/*.jsonl` for replay and attribution.

## Quick start

Full install paths, env table, data bundle, and acceptance: **[`INSTALL.md`](INSTALL.md)**.

```bash
cd nanobot-bio
bash scripts/setup_all.sh          # or: bash scripts/setup_all.sh --skip-af3
source .venv/bin/activate
nanobot-bio onboard && nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
# nanobot-bio chat
```

## Architecture

```text
User / Delivery acceptance
        │
        ▼
nanobot-bio CLI  →  Nanobot.run / run_streamed
        │
        ├─ nanobot/  (slim framework + skills + rbp tools)  ← Controller + Toolkit SoT
        ├─ app/backends/delivery  (JSON bridge)             ← read-only adapter
        └─ rbp_eval/  (offline LOO / eval-plan / evolve)     ← Validation Evaluator
                │
                ▼
        rhobind_agent_delivery  (Predictor + DBs + ready tools)
```

| Layer | Path / env | Responsibility |
|-------|------------|----------------|
| Agent Controller | in-repo `nanobot/` (`Nanobot.from_config` → `run`) | Plan tools, two LLM checkpoints, emit JSON |
| Toolkit | `nanobot/agent/tools/rbp/` + delivery scripts via bridge | Sequence / structure / function / integrate |
| Predictor | delivery `rhobind_predict` (conda `rhobind`) | Binding `prob` |
| Offline eval | `rbp_eval/` | LOO, ablations, evolve-eval (not chat) |

## Repository layout

```text
nanobot-bio/
├── app/                 # Product shell: cli/{user,accept,eval,maint}, agent, delivery bridge
├── nanobot/             # Slim vendored framework + skills/rbp-agent + agent/tools/rbp
├── config/              # defaults.yaml (Table 3) + evolved.yaml
├── rbp_eval/            # Offline evaluation / evolution
├── scripts/             # setup_all.sh, CI helpers
├── tests/               # pytest (contract / compliance)
├── docs/                # Proposal, delivery mirror, checklists (local only)
├── workspace/           # Default Nanobot workspace (skill sync target)
└── artifacts/           # Runtime reports / traces / cache (gitignored)
```

## Control flow

| Path | Steps |
|------|-------|
| **In-catalogue (Stage 0)** | `resolve_rbp` → `in_panel` → `predict_interaction` once → JSON → **STOP** |
| **Near-known** | `check_near_known` (identity ≥ 0.95) → headed donor once → JSON → **STOP** |
| **Unseen** | characterize → parallel retrieve (`hits_emb`+`hits_seq`, …) → `fuse_similarity_views` → **`confidence_abstain`** → `predict_interaction` on donors → integrate → JSON |

Defaults (Table 3 / `config/defaults.yaml`): `n_cand=5`, `tau_drop=0.30`, near-match `0.95`, label cuts `0.75/0.50/0.25`, cross-donor aggregate `weighted` (proposal §4 Σ s·p·c).

## Configuration

Defaults live in `config/defaults.yaml` (Table 3: `n_cand`, `tau_drop`, label thresholds, axes, fusion weights, abstain thresholds, llm, models). `config/evolved.yaml` is used only after offline gates pass and a candidate is promoted.

Environment variables:

| Variable | Purpose |
|----------|---------|
| `BIO_ROOT` | Parent of `nanobot-bio` and delivery |
| `DELIVERY_ROOT` | Delivery package root (`rhobind_agent_delivery`) |
| `NANOBOT_SRC` | **In-repo** slim runtime: `$NANOBOT_BIO_ROOT/nanobot` (default) |
| `NANOBOT_BIO_ROOT` | This repo root |
| `NANOBOT_WORKSPACE` | Default `nanobot-bio/workspace` |
| `NANOBOT_CONFIG` | LLM config `~/.nanobot/config.json` (unchanged) |
| `RBP_RAW_TOOLS` | `whitelist` (default) / `all` / `none` |
| `NANOBOT_TOOL_ALLOW` | ToolLoader allowlist (default `rbp`) |
| `RBP_PHMMER` | `1` to enable the optional phmmer axis |
| `HF_HOME` / `HF_ENDPOINT` | ESM weights cache / mirror |
| `OMP_NUM_THREADS` | Thread cap for embedding tools |
| `AGENT_DB` / `RBP_REGISTRY` | Injected by delivery `setup.sh` / app env |

LLM config: `nanobot-bio onboard` writes `~/.nanobot/config.json` (providers / API key). **Do not commit real API keys.**

## Commands

| Command | Audience | Purpose |
|---------|----------|---------|
| `nanobot-bio doctor` | All | Paths, registry, skill sync, axes / AF3 status |
| `nanobot-bio onboard` | User | LLM provider / API key |
| `nanobot-bio agent` / `chat` | User | Product runs (`Nanobot.run` / streamed) |
| `nanobot-bio accept-golden` | Delivery | Own-head golden (~0.966 on delivery pos RNA × PTBP1) |
| `nanobot-bio accept-llm` | Delivery | `nanobot_llm` mode + touchpoint evidence |
| `nanobot-bio gap-closure` | Delivery | Stage-0 / ordering fixture evidence pack |
| `nanobot-bio eval-plan` | Delivery / science | Ablation / metrics protocol |
| `nanobot-bio evolve` / `evolve-eval` | Science | Offline LOO batch + nested-split evolve |
| `nanobot-bio promote-evolved` | Science | Promote candidate config after gate |
| `nanobot-bio layout` / `gate` | CI | SoT layout + engineering gate |

Reports: repo `artifacts/reports/` (or `~/.nanobot-bio/artifacts/reports/` when overridden).

**Acceptance authority:** `nanobot-bio accept-golden` is the authoritative acceptance path for collaborators — it wraps and extends the delivery-native smoke assertions. `rhobind_agent_delivery/agent/examples/run_example.sh` is a delivery-only regression smoke (exercises delivery scripts directly, no app layer) and is **not** part of app acceptance; use it only when debugging a single delivery tool.

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

## Scope and boundaries

| In scope (this repo) | Out of scope |
|----------------------|--------------|
| Agent CLI, skill, curated tools, delivery **bridge** | Editing `rhobind_agent_delivery/` sources, weights, registry |
| Offline eval / evolution (`rbp_eval/`) | Online weight writes; inventing `p_hat` / `prob` |
| JSON verdict + Stage guards | Delivery **v2** tools not in registry (`score_calibration`, motif, saliency, HDOCK) |
| LLM planning + grounded explanation | Claiming calibrated P(bind) without a calibration tool + ECE evidence |

**Field semantics (acceptance wording):**

| Field | Meaning in this product |
|-------|--------------------------|
| `p_hat` | Score from predictor / `similarity_weighted_vote` (raw). Not a Delivery v2 calibrated probability. |
| `confidence` | Rules + Stage-3 checklist (and related flags). Not calibrated P(bind). |
| `label` | `{Strong, Likely, Unlikely, No}` from Table-3 cuts on `p_hat` (defaults 0.75 / 0.50 / 0.25). |

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

## Troubleshooting

Run first:

```bash
nanobot-bio doctor
```

Common issues:

- `Config missing` → run `nanobot-bio onboard`.
- `DELIVERY_ROOT missing` → check the `rhobind_agent_delivery` sibling dir or `DELIVERY_ROOT`.
- `NANOBOT_SRC missing` → expected in-repo `nanobot-bio/nanobot/` (slim vendor).
- `skill out of sync` → run `python -m app.sync_overlay` or `nanobot-bio doctor`.
- `import nanobot` points at sibling / site-packages → uninstall `nanobot-ai`, ensure `pip install -e .`, put `NANOBOT_BIO_ROOT` first on `PYTHONPATH`.
- `AF3 probe failed` → see `.af3_status`; when AF3 is unavailable the agent falls back to AFDB / sequence axis and records a caveat.
- `ESM killed/OOM (rc=-9)` → raise cgroup memory for `protein_embed`; ensure the conda env; set `HF_HOME` to local weights.
- `LLM API key missing` → `nanobot-bio onboard`.

## Version

See [`CHANGELOG.md`](CHANGELOG.md). Current release tag: **v0.5.1**.

## Docs map

| Doc | Role |
|-----|------|
| [README](README.md) / [中文](README.zh.md) | Product overview |
| [INSTALL.md](INSTALL.md) | Install / env / acceptance |
| [AGENTS.md](AGENTS.md) | Agent & CI constraints |
| [RELEASE.md](RELEASE.md) | How to cut a release |
| [CHANGELOG.md](CHANGELOG.md) | History |
| [VENDOR.md](VENDOR.md) | Slim-vendor maintainer notes |

## Acknowledgements

Slim Agent Controller derived from [Nanobot](https://github.com/HKUDS/nanobot) (vendored under `nanobot/`, channels/WebUI stripped). Scientific predictor and ready tools: `rhobind_agent_delivery` (read-only bridge). This repo does not modify delivery sources, weights, or registry.
