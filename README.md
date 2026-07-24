# nanobot-bio

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.5.1-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

**English** | [中文](README.zh.md)

Application package that answers: *Does RNA \(R\) interact with RBP \(X\)?*  
Orchestration runs on [Nanobot](https://github.com/HKUDS/nanobot). Scientific scores are produced only by tools in `rhobind_agent_delivery` (read-only from this repo).

| Document | Path | Role |
|----------|------|------|
| This README | repository root | Install, run, accept (Delivery / users) |
| Proposal (EN/ZH) | [`docs/proposal.md`](docs/proposal.md) · [`docs/proposal.zh.md`](docs/proposal.zh.md) | Task, stages, Table 2–3 |
| Delivery requirements (ZH mirror) | [`docs/delivery要求.zh.md`](docs/delivery要求.zh.md) | BUILD_SPEC / HANDOFF / registry mirror |
| Remediation checklist | [`docs/remediation-checklist.md`](docs/remediation-checklist.md) · [`docs/整改清单.zh.md`](docs/整改清单.zh.md) | Requirement × implementation matrix |

> `docs/` is local by default (gitignored except `docs/worklog/`). Ship copies to partners as needed. Machine-readable tool list: `$DELIVERY_ROOT/agent/tools/registry.json`.

---

## 1. Scope and boundaries

| In scope (this repo) | Out of scope |
|----------------------|--------------|
| Agent CLI, skill, curated tools, delivery **bridge** | Editing `rhobind_agent_delivery/` sources, weights, or registry |
| Offline eval / evolve (`rbp_eval/`) | Online weight writes; inventing `p_hat` / `prob` |
| JSON verdict schema + Stage guards | Delivery **v2** tools not in registry (`score_calibration`, motif, saliency, HDOCK) |
| LLM planning + grounded explanation | Claiming calibrated P(bind) without a calibration tool + ECE evidence |

**Field semantics (acceptance wording):**

| Field | Meaning in this product |
|-------|-------------------------|
| `p_hat` | Score from predictor / `similarity_weighted_vote` (raw). Not Delivery v2 calibrated probability. |
| `confidence` | Rules + Stage-3 checklist (and related flags). Not calibrated P(bind). |
| `label` | `{Strong, Likely, Unlikely, No}` from Table-3 cuts on `p_hat` (defaults 0.75 / 0.50 / 0.25). |

---

## 2. Architecture (Proposal §3 × Delivery layers)

```text
User / Delivery acceptance
        │
        ▼
nanobot-bio CLI  →  Nanobot.run / run_streamed
        │
        ├─ nanobot/  (skill + Tool subclasses)            ← Toolkit SoT
        ├─ app/backends/delivery  (JSON bridge)          ← read-only adapter
        └─ rbp_eval/  (offline LOO / eval-plan / evolve) ← Validation Evaluator
                │
                ▼
        rhobind_agent_delivery  (Predictor + DBs + ready tools)
```

| Layer | Path / env | Responsibility |
|-------|------------|----------------|
| Agent Controller | Nanobot + `nanobot/skills/rbp-agent/SKILL.md` | Plan tools, two LLM checkpoints, emit JSON |
| Toolkit | `nanobot/agent/tools/rbp/` + delivery scripts via bridge | Sequence / structure / function / integrate |
| Predictor | delivery `rhobind_predict` (conda `rhobind`) | Binding `prob` |
| Offline eval | `rbp_eval/` | LOO, ablations, evolve-eval (no chat path) |

---

## 3. Repository layout

```text
nanobot-bio/
  app/                 # CLI, integrate, delivery bridge, core, dev (acceptance)
  nanobot/             # SoT (Proposal §6.2): skills/rbp-agent + agent/tools/rbp
  config/defaults.yaml # Table-3 defaults, axes, fusion, models
  rbp_eval/            # Offline evaluation
  scripts/             # setup_all.sh, CI helpers
  tests/               # pytest (contract / compliance)
  docs/                # Proposal, delivery mirror, checklists (local)
  workspace/           # Default Nanobot workspace (skill sync target)
  artifacts/           # Runtime reports/traces/cache (gitignored)
```

Runtime data may also use `~/.nanobot-bio/{workspace,artifacts}` when env overrides are set. Code defaults: repo-root `artifacts/` via `app.core.paths`.
Acceptance commands are top-level CLI (`accept-golden`, `accept-llm`, `gap-closure`); helpers live in `app/dev/`.

---

## 4. Control flow (BUILD_SPEC × Proposal stages)

| Path | Steps |
|------|--------|
| **Catalogue (Stage 0)** | `resolve_rbp` → if `in_panel` → `predict_interaction` once → JSON → **STOP** |
| **Near-known** | `check_near_known` (seq identity ≥ 0.95) → headed donor once → JSON → **STOP** |
| **Unseen** | characterize → parallel retrieve (`hits_emb`+`hits_seq`, …) → `fuse_similarity_views` → **`confidence_abstain`** → `predict_interaction` on donors → integrate (`transfer_pri[...]

Defaults (Table 3 / `config/defaults.yaml`): `n_cand=5`, `tau_drop=0.30`, near-match `0.95`, label cuts `0.75/0.50/0.25`.

**Axes note:** shipped defaults enable `structure` / `rna_blastn` / `literature` with AFDB preferred; **AF3 fallback is on** (`use_af3` / `use_af3_fallback`) when AFDB misses — probe failure sur[...]

---

## 5. Requirements

- Python ≥ 3.10  
- Sibling / configured Nanobot: `$NANOBOT_SRC`  
- Delivery tree: `$DELIVERY_ROOT` (= `rhobind_agent_delivery`)  
- Optional GPU + conda envs: `protein_embed`, `rna`, `rhobind`, `af3`  
- LLM API for `agent` / `chat` / `accept-llm` (`nanobot-bio onboard`)

---

## 6. Install

### 6.1 Clone repository

#### Using HTTPS (recommended for initial setup)
```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### Using SSH (requires pre-configured SSH keys)
```bash
git clone git@github.com:JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### Using GitHub CLI (requires `gh` installed)
```bash
gh repo clone JoeSun-421/rbp-nanobot-bio
cd rbp-nanobot-bio
```

#### Specify a particular branch (e.g., develop)
```bash
git clone --branch develop https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### Specify a release tag (e.g., v0.5.1)
```bash
git clone --branch v0.5.1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### Shallow clone (download latest commit only, faster)
```bash
git clone --depth 1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### Shallow clone specific branch
```bash
git clone --branch main --depth 1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

### 6.2 Install dependencies

```bash
bash scripts/setup_all.sh
# Faster agent-focused install:
# bash scripts/setup_all.sh --skip-af3

source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
```

Environment variables (typical):

| Variable | Purpose |
|----------|---------|
| `BIO_ROOT` | Parent of `nanobot-bio` and delivery |
| `DELIVERY_ROOT` | Delivery package root |
| `NANOBOT_SRC` | Installed nanobot package or clone |
| `NANOBOT_WORKSPACE` | Default `~/.nanobot-bio/workspace` |
| `AGENT_DB` / `RBP_REGISTRY` / … | Set by delivery `setup.sh` / App env apply |

---

## 7. Commands

| Command | Audience | Purpose |
|---------|----------|---------|
| `nanobot-bio doctor` | All | Paths, registry, skill sync, axes / AF3 status |
| `nanobot-bio onboard` | User | LLM provider / API key |
| `nanobot-bio agent` / `chat` | User | Product runs (`Nanobot.run` / streamed) |
| `nanobot-bio accept-golden` | Delivery | Own-head golden (~0.966 on delivery pos RNA × PTBP1) |
| `nanobot-bio accept-llm` | Delivery | `mode=nanobot_llm` + touchpoint evidence |
| `nanobot-bio gap-closure` | Delivery | Stage-0 / order fixture evidence pack |
| `nanobot-bio eval-plan` | Delivery / science | Ablation / metrics protocol |
| `nanobot-bio layout` / `gate` | CI | SoT layout + engineering gate |

Reports: repo `artifacts/reports/` (or `~/.nanobot-bio/artifacts/reports/` when overridden).

**Acceptance authority:** `nanobot-bio accept-golden` is the authoritative acceptance path for collaborators — it wraps and extends the delivery-native smoke assertions. `rhobind_agent_delivery[...]

```bash
nanobot-bio doctor
nanobot-bio accept-golden
nanobot-bio accept-llm
nanobot-bio gap-closure
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
pytest tests/test_proposal_compliance.py -q
```

---

## 8. Configuration

| File | Content |
|------|---------|
| [`config/defaults.yaml`](config/defaults.yaml) | `n_cand`, `tau_drop`, `label_thresholds`, `axes`, `fusion_weights`, `abstain_thresholds`, `llm`, `models` |
| `config/evolved.yaml` | Used only when evolved config is promoted under offline gates |

Structure policy: prefer AFDB (`structure_fetch`) before AF3. Structure tool failure must not be encoded as similarity `0`.

---

## 9. Compliance matrix (summary)

Full matrix: [`docs/整改清单.zh.md`](docs/整改清单.zh.md).

| Area | Status vs Proposal / Delivery |
|------|-------------------------------|
| P0 tools + Stage 0 STOP | Present |
| Dual-axis seq + fuse + abstain-before-predict | Present in skill/tools |
| Integrate E1–E4 | Bridged from delivery |
| Ready-tool registration (`all`) | Present |
| Calibrated P(bind) / `score_calibration` | **Not claimed**; v2 OUT |
| Default axes all-on | Check `defaults.yaml` on the acceptance host |
| AF3 import probe | Host-dependent (see `.af3_status`) |
| Full-panel LOO / ECE reports | Commands present; numbers only if reports generated |

---

## 10. Version

See [`CHANGELOG.md`](CHANGELOG.md). Current release tag: **v0.4.0**.
