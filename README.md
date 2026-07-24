<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="480">

  <h1>nanobot-bio</h1>

  <p><b>RNA–RBP interaction prediction agent</b></p>
  <p>
    Built on <a href="https://github.com/HKUDS/nanobot">Nanobot</a>.<br/>
    Pipeline: <em>retrieve donors → borrow heads → integrate</em><br/>
    Output: auditable JSON verdict for Delivery acceptance
  </p>

  <p>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot source"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/stages-0%E2%86%921%E2%86%922%E2%86%923-green" alt="Stages">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p>
    <a href="#-clone-https">Clone</a> ·
    <a href="#overview">Overview</a> ·
    <a href="#features">Features</a> ·
    <a href="#-quick-start">Quick start</a> ·
    <a href="#architecture">Architecture</a> ·
    <a href="#configuration">Config</a> ·
    <a href="#commands">Commands</a> ·
    <a href="#testing">Tests</a> ·
    <a href="#docs">Docs</a>
  </p>

  <p><b>English</b> · <a href="README.zh.md">中文</a></p>
</div>

---

<div align="center">

### What you get

| Layer | Role |
|:-----:|:-----|
| **Agent Controller** | Slim in-repo Nanobot plans tools and runs Stage 0→3 |
| **Toolkit** | RBP tools under `nanobot/agent/tools/rbp/` |
| **Predictor** | `rhobind_agent_delivery` scores only — read-only bridge |
| **Offline eval** | `rbp_eval/` for LOO, ablations, evolve-eval |

</div>

---

## 📦 Clone (HTTPS)

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

Layout next to the science bundle:

```text
bio_agent/
├── rbp-nanobot-bio/            ← this repository
└── rhobind_agent_delivery/     ← registry · weights · DBs
```

Full install, env table, and acceptance: [`INSTALL.md`](INSTALL.md).

---

## Overview

`nanobot-bio` answers one question: **Does RNA R interact with RBP X?**

The product path is `nanobot-bio agent|chat` → `Nanobot.from_config` → `run` / `run_streamed`. A slim Nanobot tree lives under `nanobot/` as Controller + Toolkit SoT. Scores never come from the LLM: they are produced only by delivery tools behind `app/backends/delivery`. Offline LOO and self-evolution stay in `rbp_eval/`, off the chat path. The final artifact is a JSON verdict: `label`, `confidence`, `p_hat`, `explanation`, `supporting_rbps`.

---

## Features

### Agent loop

- **Stage 0→1→2→3** with two LLM checkpoints: `commit_proxy_candidates` and `normalize_verdict`.
- **Three paths**: in-catalogue own-head once then STOP; near-known Fast Path when identity ≥ 0.95; unseen retrieve → fuse → abstain → borrow heads → integrate.
- **Sequence**: dual-axis ESM-C embedding + MMseqs, not protein BLASTn.
- **Structure**: AFDB first; AF3 fallback on by default. Probe failure → caveat, never similarity `0`.
- **Contract**: `turn_guards` enforce fuse → commit → abstain → predict via `stage_contract.py`.
- **Verdict**: JSON schema + Stage-3 checklist; ≥2 failures force `confidence=low`.

### Toolkit SoT

Tools are `Tool` subclasses in `nanobot/agent/tools/rbp/` across sequence / structure / function / integrate. Delivery scripts run through the JSON bridge with subprocess isolation and separate conda envs. `RBP_RAW_TOOLS=whitelist` is the curated default; `all` opens the full 37-tool set for debugging; `RBP_PHMMER=1` adds the optional phmmer axis.

### Offline evaluation & evolution

`rbp_eval/` runs leave-one-RBP-out, ablations, and evolve-eval. Self-evolution is offline: `evolve-eval` writes a candidate; promote when `delta_auprc > 0` or HOLD into `config/evolved.yaml`. `RBPTraceHook` records `artifacts/traces/*.jsonl` for replay.

---

## ⚡ Quick start

```bash
bash scripts/setup_all.sh
# lighter path: bash scripts/setup_all.sh --skip-af3
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
              nanobot-bio CLI → Nanobot.run / run_streamed
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
     nanobot/          app/backends/           rbp_eval/
   Controller+Toolkit   delivery bridge      offline evaluator
          │                   │
          └─────────┬─────────┘
                    ▼
         rhobind_agent_delivery
         Predictor · DBs · ready tools
```

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Agent Controller | in-repo `nanobot/` | Plan tools, checkpoints, emit JSON |
| Toolkit | `nanobot/agent/tools/rbp/` + bridge | Sequence / structure / function / integrate |
| Predictor | delivery `rhobind_predict` | Binding `prob` |
| Offline eval | `rbp_eval/` | LOO · ablations · evolve-eval |

---

## Repository layout

```text
nanobot-bio/
├── app/          Product shell — cli/{user,accept,eval,maint} · agent · bridge
├── nanobot/      Slim framework · skills/rbp-agent · agent/tools/rbp
├── config/       defaults.yaml Table 3 · evolved.yaml
├── rbp_eval/     Offline evaluation / evolution
├── scripts/      setup_all.sh · CI helpers
├── tests/        pytest
├── docs/         Local-only proposal & checklists
├── workspace/    Nanobot workspace · skill sync target
└── artifacts/    reports · traces · cache — gitignored
```

---

## Control flow

| Path | Steps |
|------|-------|
| **In-catalogue** | `resolve_rbp` → `in_panel` → `predict_interaction` ×1 → JSON → **STOP** |
| **Near-known** | `check_near_known` identity ≥ 0.95 → headed donor ×1 → JSON → **STOP** |
| **Unseen** | characterize → `hits_emb`+`hits_seq` → `fuse_similarity_views` → `confidence_abstain` → predict donors → integrate → JSON |

Table 3 defaults in `config/defaults.yaml`: `n_cand=5`, `tau_drop=0.30`, near-match `0.95`, label cuts `0.75 / 0.50 / 0.25`, aggregate `weighted` per proposal §4.

---

## Configuration

Authoritative knobs: `config/defaults.yaml`. Promoted candidates: `config/evolved.yaml`.

| Variable | Purpose |
|----------|---------|
| `BIO_ROOT` | Parent of this repo and delivery |
| `DELIVERY_ROOT` | `rhobind_agent_delivery` root |
| `NANOBOT_SRC` | In-repo Nanobot — default `$NANOBOT_BIO_ROOT/nanobot` |
| `NANOBOT_BIO_ROOT` | This repo root |
| `NANOBOT_WORKSPACE` | Default `workspace/` |
| `NANOBOT_CONFIG` | `~/.nanobot/config.json` |
| `RBP_RAW_TOOLS` | `whitelist` · `all` · `none` |
| `NANOBOT_TOOL_ALLOW` | ToolLoader allowlist — default `rbp` |
| `RBP_PHMMER` | `1` enables phmmer axis |
| `HF_HOME` / `HF_ENDPOINT` | ESM cache / mirror |
| `OMP_NUM_THREADS` | Embedding thread cap |

`nanobot-bio onboard` writes provider + API key. **Never commit secrets.**

---

## Commands

| Command | Audience | Purpose |
|---------|----------|---------|
| `doctor` | All | Paths · registry · skill · axes / AF3 |
| `onboard` | User | LLM provider / API key |
| `agent` / `chat` | User | Product path |
| `accept-golden` | Delivery | Own-head golden ≈0.966 PTBP1 × pos RNA |
| `accept-llm` | Delivery | LLM touchpoint evidence |
| `gap-closure` | Delivery | Stage-0 / order fixtures |
| `eval-plan` | Science | Ablations / metrics |
| `evolve` / `evolve-eval` | Science | Offline self-evolution |
| `promote-evolved` | Science | Promote after gate |
| `layout` / `gate` | CI | SoT + engineering gate |

Reports → `artifacts/reports/`. Authoritative acceptance: **`accept-golden`**. Delivery-only smoke `agent/examples/run_example.sh` is not app acceptance.

### Chat slash commands

`/help` · `/status` · `/tools` · `/new` · `/clear` · `/thinking` · `/onboard` · `/quit`

---

## Scope and boundaries

| In scope | Out of scope |
|----------|--------------|
| CLI · skill · curated tools · delivery bridge | Editing delivery sources / weights / registry |
| Offline `rbp_eval/` | Online weight writes · inventing `p_hat` |
| JSON verdict + Stage guards | Unregistered Delivery v2 tools |
| Grounded LLM explanation | Calibrated P(bind) without ECE |

| Field | Meaning |
|-------|---------|
| `p_hat` | Raw predictor / vote score |
| `confidence` | Rules + Stage-3 checklist |
| `label` | `Strong` · `Likely` · `Unlikely` · `No` |

---

## Testing

```bash
python -m pytest -q                                          # 120 passed
pytest tests/test_proposal_compliance.py \
       tests/test_stage_contract.py \
       tests/test_section4_fidelity.py -q
```

---

## Troubleshooting

Start with `nanobot-bio doctor`.

| Symptom | Fix |
|---------|-----|
| Config missing | `nanobot-bio onboard` |
| `DELIVERY_ROOT` missing | Sibling delivery dir or set env |
| Wrong `import nanobot` | Uninstall `nanobot-ai` · `pip install -e .` |
| Skill out of sync | `python -m app.sync_overlay` |
| AF3 probe failed | Caveat + AFDB / seq fallback |
| ESM OOM `rc=-9` | Raise cgroup RAM · set `HF_HOME` |

---

## Docs

| Doc | Role |
|-----|------|
| [INSTALL.md](INSTALL.md) | Install · env · acceptance |
| [AGENTS.md](AGENTS.md) | Agent & CI gates |
| [RELEASE.md](RELEASE.md) | Release process |
| [CHANGELOG.md](CHANGELOG.md) | History · **v0.5.1** |
| [VENDOR.md](VENDOR.md) | Slim-vendor notes |
| [README.zh.md](README.zh.md) | 中文 |

---

<div align="center">

**Acknowledgements**

Controller from [HKUDS/nanobot](https://github.com/HKUDS/nanobot) · slim vendor under `nanobot/`.<br/>
Predictor & ready tools from `rhobind_agent_delivery` via read-only bridge.<br/>
This repository does not modify delivery sources, weights, or registry.

</div>
