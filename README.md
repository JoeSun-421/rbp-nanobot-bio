<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="460">
  <h1>nanobot-bio</h1>
  <p><b>RNA–RBP interaction prediction agent</b></p>
  <p>Orchestrates <em>retrieve → borrow heads → integrate</em> and emits an auditable JSON verdict.<br/>
  Built on <a href="https://github.com/HKUDS/nanobot">Nanobot</a> · scores from <code>rhobind_agent_delivery</code> (read-only bridge).</p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/stages-0%E2%86%921%E2%86%922%E2%86%923-green" alt="Stages">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
  <p><b>English</b> · <a href="README.zh.md">中文</a></p>
</div>

---

## 🧭 Navigation

| | |
|---|---|
| [📦 Clone](#-clone-https) | [⚡ Quick start](#-quick-start) |
| [🏗️ Architecture](#️-architecture) | [📁 Layout](#-repository-layout) |
| [🔀 Control flow](#-control-flow) | [⚙️ Configuration](#️-configuration) |
| [💻 Commands](#-commands) | [🧪 Testing](#-testing) |
| [🔧 Troubleshooting](#-troubleshooting) | [📚 Docs](#-docs) |

---

## 📦 Clone (HTTPS)

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

Place the delivery bundle as a **sibling** directory (not inside this repo):

```text
bio_agent/
├── rbp-nanobot-bio/          # this repository
└── rhobind_agent_delivery/   # science bundle (registry, weights, DBs)
```

Full install / env / acceptance: **[`INSTALL.md`](INSTALL.md)**.

---

## ⚡ Quick start

```bash
bash scripts/setup_all.sh          # or: --skip-af3 / --skip-conda
source .venv/bin/activate
nanobot-bio onboard && nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
# nanobot-bio chat
```

---

## ✨ Capabilities

| Area | Highlights |
|------|------------|
| **Stages** | `0→1→2→3` with two LLM checkpoints (`commit_proxy_candidates`, `normalize_verdict`) |
| **Paths** | In-catalogue (own-head → STOP) · near-known (identity ≥ 0.95) · unseen (retrieve → fuse → abstain → predict → integrate) |
| **Sequence** | Dual-axis: ESM-C embedding + MMseqs |
| **Structure** | AFDB first; AF3 fallback on by default (probe miss → caveat, never sim `0`) |
| **Contract** | `turn_guards` enforce fuse → commit → abstain → predict |
| **Verdict** | JSON schema + Stage-3 checklist (≥2 failures → `confidence=low`) |
| **Toolkit** | `nanobot/agent/tools/rbp/` · four views · delivery via JSON bridge |
| **Eval** | `rbp_eval/` offline only (LOO / ablations / evolve-eval) |

---

## 🏗️ Architecture

```text
User / Delivery acceptance
        │
        ▼
nanobot-bio CLI  →  Nanobot.run / run_streamed
        │
        ├─ nanobot/                 Controller + Toolkit SoT
        ├─ app/backends/delivery    read-only JSON bridge
        └─ rbp_eval/                offline Validation Evaluator
                │
                ▼
        rhobind_agent_delivery      Predictor + DBs + ready tools
```

| Layer | Location | Role |
|-------|----------|------|
| Agent Controller | in-repo `nanobot/` | Plan tools, checkpoints, emit JSON |
| Toolkit | `nanobot/agent/tools/rbp/` + bridge | Sequence / structure / function / integrate |
| Predictor | delivery `rhobind_predict` | Binding `prob` |
| Offline eval | `rbp_eval/` | LOO, ablations, evolve-eval |

---

## 📁 Repository layout

```text
nanobot-bio/
├── app/          # Product shell: cli/{user,accept,eval,maint}, agent, bridge
├── nanobot/      # Slim runtime + skills/rbp-agent + agent/tools/rbp
├── config/       # defaults.yaml (Table 3) + evolved.yaml
├── rbp_eval/     # Offline evaluation / evolution
├── scripts/      # setup_all.sh, CI helpers
├── tests/        # pytest
├── docs/         # Local-only (not on GitHub)
├── workspace/    # Nanobot workspace (skill sync target)
└── artifacts/    # reports / traces / cache (gitignored)
```

---

## 🔀 Control flow

| Path | Steps |
|------|-------|
| **In-catalogue** | `resolve_rbp` → `in_panel` → `predict_interaction` ×1 → JSON → **STOP** |
| **Near-known** | `check_near_known` (≥0.95) → headed donor ×1 → JSON → **STOP** |
| **Unseen** | characterize → retrieve → `fuse_similarity_views` → `confidence_abstain` → predict donors → integrate → JSON |

Defaults (`config/defaults.yaml`): `n_cand=5`, `tau_drop=0.30`, near-match `0.95`, label cuts `0.75/0.50/0.25`, aggregate `weighted`.

---

## ⚙️ Configuration

Table-3 defaults: `config/defaults.yaml`. Promoted candidates: `config/evolved.yaml`.

| Variable | Purpose |
|----------|---------|
| `BIO_ROOT` | Parent of this repo and delivery |
| `DELIVERY_ROOT` | `rhobind_agent_delivery` root |
| `NANOBOT_SRC` | In-repo runtime (`$NANOBOT_BIO_ROOT/nanobot`) |
| `NANOBOT_BIO_ROOT` | This repo root |
| `NANOBOT_WORKSPACE` | Default `workspace/` |
| `NANOBOT_CONFIG` | `~/.nanobot/config.json` |
| `RBP_RAW_TOOLS` | `whitelist` / `all` / `none` |
| `NANOBOT_TOOL_ALLOW` | ToolLoader allowlist (default `rbp`) |
| `RBP_PHMMER` | `1` = enable phmmer axis |
| `HF_HOME` / `HF_ENDPOINT` | ESM cache / mirror |
| `OMP_NUM_THREADS` | Embedding thread cap |

LLM keys via `nanobot-bio onboard` → `~/.nanobot/config.json`. **Never commit API keys.**

---

## 💻 Commands

| Command | Purpose |
|---------|---------|
| `doctor` | Paths, registry, skill sync, axes / AF3 |
| `onboard` | LLM provider / API key |
| `agent` / `chat` | Product runs (`Nanobot.run` / streamed) |
| `accept-golden` | Own-head golden (~0.966 PTBP1 × pos RNA) |
| `accept-llm` | LLM touchpoint evidence |
| `gap-closure` | Stage-0 / order fixtures |
| `eval-plan` | Ablations / metrics |
| `evolve` / `evolve-eval` | Offline self-evolution |
| `promote-evolved` | Promote candidate after gate |
| `layout` / `gate` | SoT + engineering gate |

Reports → `artifacts/reports/`. Authoritative acceptance: **`accept-golden`**.

<details>
<summary>Chat slash commands</summary>

| Command | Purpose |
|---------|---------|
| `/help` `/status` `/tools` | Help / model+tools / list tools |
| `/new` `/clear` `/thinking` | New session / clear / toggle thinking |
| `/onboard` `/quit` | Reconfigure LLM / exit |

</details>

---

## 🎯 Scope

| In scope | Out of scope |
|----------|--------------|
| CLI, skill, curated tools, delivery **bridge** | Editing delivery sources / weights / registry |
| Offline eval (`rbp_eval/`) | Online weight writes; inventing `p_hat` |
| JSON verdict + Stage guards | Unregistered Delivery v2 tools |
| Grounded LLM explanation | Calibrated P(bind) without ECE evidence |

| Field | Meaning |
|-------|---------|
| `p_hat` | Raw predictor / vote score (not calibrated P) |
| `confidence` | Rules + Stage-3 checklist |
| `label` | `Strong` / `Likely` / `Unlikely` / `No` (Table-3 cuts) |

---

## 🧪 Testing

```bash
python -m pytest -q
# 120 passed

pytest tests/test_proposal_compliance.py tests/test_stage_contract.py tests/test_section4_fidelity.py -q
```

---

## 🔧 Troubleshooting

```bash
nanobot-bio doctor
```

| Symptom | Fix |
|---------|-----|
| Config missing | `nanobot-bio onboard` |
| `DELIVERY_ROOT` missing | Sibling `rhobind_agent_delivery` or set env |
| Wrong `import nanobot` | Uninstall `nanobot-ai`; `pip install -e .` |
| Skill out of sync | `python -m app.sync_overlay` |
| AF3 probe failed | Caveat + AFDB/seq fallback (expected when AF3 unavailable) |
| ESM OOM (`rc=-9`) | Raise cgroup RAM; set `HF_HOME` |

---

## 📚 Docs

| Doc | Role |
|-----|------|
| [INSTALL.md](INSTALL.md) | Install / env / acceptance |
| [AGENTS.md](AGENTS.md) | Agent & CI constraints |
| [RELEASE.md](RELEASE.md) | Release process |
| [CHANGELOG.md](CHANGELOG.md) | History · **v0.5.1** |
| [VENDOR.md](VENDOR.md) | Slim-vendor notes |
| [README.zh.md](README.zh.md) | 中文 |

---

## 🙏 Acknowledgements

Controller derived from [Nanobot](https://github.com/HKUDS/nanobot) (slim vendor under `nanobot/`). Predictor & tools: `rhobind_agent_delivery` via read-only bridge — this repo does not modify delivery sources, weights, or registry.
