```
                    ╔═══════════════════════════════════╗
                    ║      NANOBOT-BIO                  ║
                    ║  RNA-RBP Interaction Prediction   ║
                    ╚═══════════════════════════════════╝
```

**Runs on:** [**Nanobot**](https://github.com/HKUDS/nanobot) (official repo)

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.5.1-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/JoeSun-421/rbp-nanobot-bio)](https://github.com/JoeSun-421/rbp-nanobot-bio/issues)

**English** | [中文](README.zh.md)

---

## Overview

Computational pipeline to predict RNA–RBP (RNA-binding protein) interactions using multi-modal evidence: sequence homology, structural similarity, domain composition, and literature co-occurrence. The system orchestrates these modalities through a two-layer architecture:

1. **Application Layer** (`nanobot-bio`): Planning, tool sequencing, confidence rules, JSON schema
2. **Science Kernel** (`rhobind_agent_delivery`): Predictor models, curated databases, molecular representations

Scientific scores are produced exclusively by the delivery layer. This repository provides orchestration, evaluation protocols, and deployment logic.

---

## 📋 Table of Contents

- [Background](#background)
- [Architecture](#architecture)
- [Scope](#scope--boundaries)
- [Quick Start](#-quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Output Format](#output-format)
- [Troubleshooting](#troubleshooting)
- [Configuration](#configuration)
- [Resources](#resources)

---

## Background

### Why Two Repositories?

RNA–RBP interactions are central to post-transcriptional gene regulation but difficult to predict at scale. Experimental characterization (CLIP-seq, RIP, etc.) is expensive; computational methods must integrate multiple weak signals.

**nanobot-bio** separates concerns:
- **Delivery** (science team): Train models, curate RBP/RNA databases, maintain predictor registry
- **Application** (integration team): Orchestrate tools, manage evidence fusion, validate predictions

This separation enables:
- **Parallel development:** predictor improvements without app iteration
- **Multiple frontends:** same predictor can serve web UI, CLI, batch pipeline
- **Reproducible evaluation:** offline protocols (LOO, ablation) independent of online queries

### Design

The system stages predictions to handle varying evidence availability:

- **Stage 0 (RBP in panel):** Direct own-head predictor; if confidence high, stop.
- **Stage 1 (near-known):** High-identity sequence match (≥95%) to annotated RNA–RBP pair; use existing donor prediction.
- **Stage 2 (evidence gathering):** Retrieve sequence and structural homologs; compute fusion score.
- **Stage 3 (scoring):** Predict on selected donors; aggregate with confidence checklist.

Default axes:
- **Structure:** AFDB alignments via Foldseek (AF3 fallback on miss)
- **Sequence:** ESM-C embeddings + MMseqs
- **Literature:** Curated co-occurrence knowledge

---

## Architecture

```text
┌──────────────────────────────────────────┐
│  nanobot-bio (this repo)                 │  Orchestration
│  ├─ CLI, skill, tool registry bridge     │  Stage guards
│  ├─ LLM planning & confidence rules      │  JSON verdict
│  └─ Offline eval & self-evolution        │
└────────────────────┬─────────────────────┘
                     │ (reads from)
┌────────────────────▼─────────────────────┐
│  rhobind_agent_delivery ($DELIVERY_ROOT) │  Science Kernel
│  ├─ Predictor models (ESM, AF3, etc.)    │  Curated databases
│  ├─ Tool implementations                 │  RBP/RNA annotations
│  └─ Ready-to-use registry                │
└──────────────────────────────────────────┘
```

**Data flow:**
1. User query (RNA seq, RBP name) → **Nanobot CLI**
2. **nanobot-bio** plans tool sequence (retrieve, score, integrate)
3. Tools invoke **delivery** layer (sandbox subprocess or HTTP)
4. Results fuse through **ensemble aggregation**
5. **Confidence rules** append Stage-3 checklist
6. JSON verdict returned

---

## 1. Scope & Boundaries

| In Scope (This Repo) | Out of Scope |
|---|---|
| Agent CLI, skill, curated tools, delivery bridge | Editing `rhobind_agent_delivery/` sources, weights, or registry |
| Offline eval / evolve (`rbp_eval/`) | Online weight writes; inventing `p_hat` / `prob` |
| JSON verdict schema + Stage guards | Delivery **v2** tools not in registry |
| LLM planning + grounded explanation | Claiming calibrated P(bind) without calibration evidence |

**Field semantics:**

| Field | Meaning |
|-------|---------|
| `p_hat` | Raw prediction score (0–1) from ensemble. **Not** calibrated probability. |
| `confidence` | Stage-3 rules + checklist (Strong/Likely/Unlikely/No). **Not** P(bind). |
| `label` | Classification based on `p_hat` thresholds (default: 0.75 / 0.50 / 0.25). |
| `caveats` | Reliability flags: e.g., `low_head_coverage`, `structure_axis_unavailable`. |

---

## 2. Repository Layout

```text
nanobot-bio/
  ├─ app/                 # CLI, integration, delivery bridge
  ├─ nanobot/             # SoT: skills/rbp-agent + agent/tools/rbp
  ├─ config/defaults.yaml # Default parameters, axes, models, thresholds
  ├─ rbp_eval/            # Offline evaluation, ablation, self-evolution
  ├─ scripts/             # setup_all.sh, CI helpers
  ├─ tests/               # pytest contract tests
  ├─ docs/                # Proposal, guides, checklists
  ├─ workspace/           # Default Nanobot workspace (symlink)
  └─ artifacts/           # Runtime reports, cache (gitignored)
```

---

## 3. Requirements

- **Python ≥ 3.10**
- **Nanobot:** `$NANOBOT_SRC` (install via `pip install nanobot` or clone from [HKUDS/nanobot](https://github.com/HKUDS/nanobot))
- **Delivery:** `$DELIVERY_ROOT` (path to `rhobind_agent_delivery/`)
- **Optional:** GPU + conda envs for `protein_embed`, `rna`, `rhobind`, `af3`
- **LLM API:** Required for `agent` / `chat` / `accept-llm` commands (OpenAI, Anthropic, etc.)

---

## 🚀 Quick Start

Get predictions in 5 minutes:

```bash
# 1. Clone
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

# 2. Install (fast: skip AF3)
bash scripts/setup_all.sh --skip-af3
source .venv/bin/activate

# 3. Configure LLM
nanobot-bio onboard

# 4. Verify environment
nanobot-bio doctor

# 5. Predict
nanobot-bio agent --message "Does RNA GGCGGAGGAGGAGGA interact with RBP PTBP1?"
```

**Expected output:**
```json
{
  "p_hat": 0.78,
  "confidence": "Likely",
  "label": "Likely",
  "explanation": "Sequence similarity + domain match (RRM) + 4 known donors",
  "caveats": [],
  "tools_used": ["resolve_rbp", "fuse_similarity_views", "predict_interaction"],
  "latency_ms": 42000
}
```

---

## Installation

### Step 1: Clone Repository

#### Using HTTPS (recommended)
```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### Using SSH
```bash
git clone git@github.com:JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### Using GitHub CLI
```bash
gh repo clone JoeSun-421/rbp-nanobot-bio
cd rbp-nanobot-bio
```

#### Shallow clone (faster)
```bash
git clone --depth 1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

### Step 2: Install Dependencies

#### Full installation (includes AF3, ~1 hour on fast connection)
```bash
bash scripts/setup_all.sh
source .venv/bin/activate
nanobot-bio onboard  # Configure LLM API
nanobot-bio doctor   # Verify environment
```

#### Fast installation (skip AF3, ~10 min)
```bash
bash scripts/setup_all.sh --skip-af3
source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
```

### Step 3: Set Environment Variables

| Variable | Required | Default | Example |
|----------|----------|---------|---------|
| `DELIVERY_ROOT` | ✅ Yes | None | `/data/rhobind_agent_delivery` |
| `NANOBOT_SRC` | For dev | Auto (pip) | `~/git/nanobot` |
| `BIO_ROOT` | No | Auto | `/data/projects` |
| `NANOBOT_WORKSPACE` | No | `~/.nanobot-bio/workspace` | — |

**⚠️ Critical:** Set `DELIVERY_ROOT` first. All tools fail without it:

```bash
export DELIVERY_ROOT=/path/to/rhobind_agent_delivery
nanobot-bio doctor  # Should now list all tools
```

---

## Usage

### Run Predictions

```bash
# Single query
nanobot-bio agent --message "Does RNA GGCGGAGGAGGAGGA interact with RBP PTBP1?"

# Streaming output (slower, real-time)
nanobot-bio chat --message "Does RNA GGCGGAGGAGGAGGA interact with RBP PTBP1?"

# From file
nanobot-bio agent --message "$(cat query.txt)"
```

### Verify Setup

```bash
nanobot-bio doctor
# Output:
#   ✅ Python 3.10.5
#   ✅ DELIVERY_ROOT: /data/rhobind_agent_delivery
#   ✅ NANOBOT_SRC: nanobot (pip)
#   ✅ Registry: 42 tools available
#   ⚠️  AF3: deferred (set AF3_CKPT to enable)
```

### Run Tests

```bash
# All tests
pytest tests/

# Fast compliance check
pytest tests/test_proposal_compliance.py -q

# With coverage
pytest tests/ --cov=app --cov=rbp_eval --cov-report=html
```

### Advanced Commands (Maintainers)

| Command | Purpose |
|---------|---------|
| `nanobot-bio accept-golden` | Authoritative acceptance test (requires GPU) |
| `nanobot-bio accept-llm` | LLM-based verdict validation |
| `nanobot-bio eval-plan` | Ablation study & metrics protocol |
| `nanobot-bio layout` / `gate` | SoT validation + engineering checks |

---

## Output Format

### Typical Verdict JSON

```json
{
  "p_hat": 0.78,
  "confidence": "Likely",
  "label": "Likely",
  "explanation": "Sequence similarity with 4 known donors (≥0.50 p_hat) + domain match (RRM) support binding.",
  "caveats": [],
  "tools_used": [
    "resolve_rbp",
    "fuse_similarity_views",
    "predict_interaction"
  ],
  "latency_ms": 42000
}
```

### Interpreting Results

- **Confidence = "Strong"** → p_hat ≥ 0.75 & checklist passed → **High confidence**
- **Confidence = "Likely"** → p_hat ≥ 0.50 & moderate evidence → **Probable interaction**
- **Confidence = "Unlikely"** → p_hat < 0.50 → **Unlikely interaction**
- **Confidence = "No"** → p_hat < 0.25 → **No interaction**

### Caveats to Watch

- `low_head_coverage` → Predictor has few donors (high uncertainty)
- `structure_axis_unavailable` → AF3 failed; used AFDB instead
- `domain_empty` → No domain annotation found
- `af3_fallback_used` → AFDB unavailable; AF3 backbone used

---

## Performance Benchmarks

On an **A100 GPU** with default config:

| Scenario | Time | GPU Memory |
|----------|------|-----------|
| Stage 0 (RBP in panel) | <1s | — |
| Near-known (seq match ≥95%) | 10–30s | 4GB |
| Unseen (full pipeline, no AF3) | 2–3 min | 8GB |
| Unseen (with AF3 fallback) | 30–60 min | 20GB |

**CPU mode:** ~100× slower (not recommended).

---

## Troubleshooting

### Q1: `DELIVERY_ROOT` not found

**Error:**
```
FileNotFoundError: /data/rhobind_agent_delivery/agent/tools/registry.json
```

**Fix:**
```bash
# Verify delivery package exists
ls $DELIVERY_ROOT/agent/tools/registry.json

# If missing, set correct path
export DELIVERY_ROOT=/correct/path
nanobot-bio doctor
```

### Q2: GPU out of memory

**Error:**
```
CUDA out of memory: tried to allocate 2.5 GiB on GPU 0
```

**Solutions:**
- Use `--skip-af3` during install
- Skip AF3 fallback: `AF3_SKIP=1 nanobot-bio agent ...`
- Use smaller models: `RBP_MODEL=esm2_t6_8m nanobot-bio agent ...`

### Q3: Nanobot import fails

**Error:**
```
ModuleNotFoundError: No module named 'nanobot'
```

**Fix:**
```bash
# Check installation
python -c "import nanobot; print(nanobot.__file__)"

# If needed, use local clone
export NANOBOT_SRC=~/git/nanobot
nanobot-bio doctor
```

### Q4: AF3 weights download stuck

**Error:**
```
Timeout downloading AF3 weights (100+ GB)
```

**Solutions:**
- Ensure stable internet & sufficient disk space (150GB)
- Skip for now: `bash scripts/setup_all.sh --skip-af3`
- Resume later: `python -m app.models.af3_setup --resume`

### Q5: LLM API errors

**Error:**
```
AuthenticationError: Invalid API key
```

**Fix:**
```bash
nanobot-bio onboard  # Reconfigure
# or set manually:
export OPENAI_API_KEY=sk-...
```

---

## Configuration

Edit [`config/defaults.yaml`](config/defaults.yaml) to adjust:

```yaml
# Ensemble parameters
n_cand: 5              # Max candidate donors
tau_drop: 0.30         # Min similarity to keep candidate

# Evidence axes
axes:
  structure: true      # Structural alignment (Foldseek)
  rna_blastn: true     # Sequence homology (MMseqs)
  literature: true     # Co-occurrence knowledge

# Confidence thresholds (Table 3)
label_thresholds:
  strong: 0.75
  likely: 0.50
  unlikely: 0.25

# AF3 fallback (when AFDB miss)
structure_policy:
  use_af3: false
  use_af3_fallback: true

# LLM for planning & explanation
llm:
  model: gpt-4o
  temperature: 0.2
```

---

## Known Limitations

- **Light LOO** uses CSV lookup; full FASTA recompute deferred
- **Label calibration** requires ground-truth pairs (not all datasets available)
- **AF3 fallback** adds 30–60 min latency per RNA (GPU required)
- **Delivery v2 calibration** not available in this version
- **Parallel retrieve** is hardware-dependent; some GPUs may hit memory limits
- **No batch inference** (single RNA per query; loop in shell for bulk)

---

## Contributing

We welcome bug reports, feature requests, and pull requests!

### Report an Issue

Open an [issue](https://github.com/JoeSun-421/rbp-nanobot-bio/issues) with:
- Clear description of the problem
- Steps to reproduce
- Environment info (Python version, GPU, OS)

### Submit a Pull Request

1. Fork this repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and run tests: `pytest tests/`
4. Format code: `ruff check . && ruff format .`
5. Push and open a PR

---

## Testing

```bash
# Full test suite
pytest tests/

# Specific test file
pytest tests/test_proposal_compliance.py -v

# Fast lint check
ruff check .
```

---

## Resources

- **[Nanobot Framework](https://github.com/HKUDS/nanobot)** — Official orchestration engine
- **[Full Proposal](docs/proposal.md)** — Scientific specification (Table 2–3, stages, axes)
- **[Engineering Guide](docs/工程指南.zh.md)** — Development workflow & CI gates
- **[Delivery Requirements](docs/delivery要求.zh.md)** — Tool registry & handoff spec
- **[Changelog](CHANGELOG.md)** — Release notes & version history
- **[Issues](https://github.com/JoeSun-421/rbp-nanobot-bio/issues)** — Bug reports & feature requests
- **[Discussions](https://github.com/JoeSun-421/rbp-nanobot-bio/discussions)** — Q&A & community

---

## Version

Current release: **v0.5.1**  
See [`CHANGELOG.md`](CHANGELOG.md) for details.

---

## License

[MIT License](LICENSE) — see LICENSE file for details.

## Citation

If you use **nanobot-bio** in your research, please cite:

```bibtex
@software{nanobot_bio_2026,
  title={nanobot-bio: RNA-RBP Interaction Prediction via Multi-Modal Fusion},
  author={Sun, Zhaoyuan and others},
  url={https://github.com/JoeSun-421/rbp-nanobot-bio},
  year={2026},
  version={0.5.1}
}
```

---

## Acknowledgments

- [Nanobot](https://github.com/HKUDS/nanobot) team for the orchestration framework
- [rhobind_agent_delivery](https://github.com/HKUDS/rhobind_agent_delivery) team for predictor & databases
- All contributors and users for feedback & improvements
