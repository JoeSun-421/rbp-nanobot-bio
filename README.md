# nanobot-bio

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.5.1-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/JoeSun-421/rbp-nanobot-bio)](https://github.com/JoeSun-421/rbp-nanobot-bio/issues)

**English** | [中文](README.zh.md)

Application package that answers: *Does RNA \(R\) interact with RBP \(X\)?*  
Orchestration runs on [Nanobot](https://github.com/HKUDS/nanobot). Scientific scores are produced only by tools in `rhobind_agent_delivery` (read-only from this repo).

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Output Format](#output-format)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)
- [Resources](#resources)

---

## 🚀 Quick Start

Get predictions in 5 minutes:

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
bash scripts/setup_all.sh --skip-af3  # Skip AF3 for faster first run
source .venv/bin/activate
nanobot-bio onboard                    # Configure LLM API
nanobot-bio agent --message "Does RNA GGCGGAGGAGGAGGA interact with RBP PTBP1?"
```

**Expected output:**
```json
{
  "p_hat": 0.78,
  "confidence": "Likely",
  "label": "Likely",
  "caveats": []
}
```

Run `nanobot-bio doctor` to verify your environment.

---

## Architecture: Why Two Repositories?

```text
┌─────────────────────────────────────┐
│  nanobot-bio (this repo)            │  Application Orchestration Layer
│  • LLM planning & tool sequencing   │  • JSON verdict formatting
│  • Stage guards & confidence rules  │  • Read-only bridge to delivery
└──────────────────────┬──────────────┘
                       │ (reads from)
┌──────────────────────▼──────────────┐
│  rhobind_agent_delivery             │  Science Kernel ($DELIVERY_ROOT)
│  • Predictor models                 │  • Curated RBP/RNA databases
│  • Tool implementations             │  • Owned by delivery team
└─────────────────────────────────────┘
```

**Benefit:** App innovation without retraining models. Delivery reuse across multiple frontends.

---

## 1. Scope and boundaries

| In scope (this repo) | Out of scope |
|----------------------|--------------|
| Agent CLI, skill, curated tools, delivery **bridge** | Editing `rhobind_agent_delivery/` sources, weights, or registry |
| Offline eval / evolve (`rbp_eval/`) | Online weight writes; inventing `p_hat` / `prob` |
| JSON verdict schema + Stage guards | Delivery **v2** tools not in registry (`score_calibration`, motif, saliency, HDOCK) |
| LLM planning + grounded explanation | Claiming calibrated P(bind) without a calibration tool + ECE evidence |

**Field semantics (what each field means in our product):**

| Field | Meaning |
|-------|---------|
| `p_hat` | Raw score from predictor (0–1). **Not** calibrated probability. |
| `confidence` | Stage-3 rules + checklist (Strong/Likely/Unlikely/No). **Not** P(bind). |
| `label` | Classification based on `p_hat` thresholds (default: 0.75/0.50/0.25). |
| `caveats` | Reliability warnings (e.g., `low_head_coverage`, `structure_axis_unavailable`). |

---

## 2. Repository layout

```text
nanobot-bio/
  ├─ app/                 # CLI, integration, delivery bridge
  ├─ nanobot/             # SoT: skills/rbp-agent + agent/tools/rbp
  ├─ config/defaults.yaml # Default parameters, axes, models
  ├─ rbp_eval/            # Offline evaluation & evolution
  ├─ scripts/             # setup_all.sh, CI helpers
  ├─ tests/               # pytest contract tests
  ├─ docs/                # Proposal, guides, checklists
  ├─ workspace/           # Default Nanobot workspace (symlink)
  └─ artifacts/           # Runtime reports, cache (gitignored)
```

---

## 3. Requirements

- **Python ≥ 3.10**
- **Nanobot:** `$NANOBOT_SRC` (install via `pip install nanobot` or point to clone)
- **Delivery:** `$DELIVERY_ROOT` (path to `rhobind_agent_delivery/`)
- **Optional:** GPU + conda envs for `protein_embed`, `rna`, `rhobind`, `af3`
- **LLM API:** Required for `agent` / `chat` / `accept-llm` commands

---

## Installation

### Step 1: Clone repository

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

#### Shallow clone (faster, for latest commit only)
```bash
git clone --depth 1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

### Step 2: Install dependencies

#### Full installation (includes AF3, ~1 hour)
```bash
bash scripts/setup_all.sh
source .venv/bin/activate
nanobot-bio onboard  # Configure LLM API (OpenAI, Anthropic, etc.)
nanobot-bio doctor   # Verify setup
```

#### Fast installation (skip AF3, ~10 min)
```bash
bash scripts/setup_all.sh --skip-af3
source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
```

### Step 3: Configure environment variables

| Variable | Required | Default | Example |
|----------|----------|---------|---------|
| `DELIVERY_ROOT` | ✅ **Yes** | None | `/data/rhobind_agent_delivery` |
| `NANOBOT_SRC` | For dev | Auto (pip) | `~/git/nanobot` |
| `BIO_ROOT` | No | Auto | `/data/projects` |
| `NANOBOT_WORKSPACE` | No | `~/.nanobot-bio/workspace` | — |

**⚠️ Common error:** Forgetting `DELIVERY_ROOT` → all tools fail. Set it first:

```bash
export DELIVERY_ROOT=/path/to/rhobind_agent_delivery
nanobot-bio doctor  # Should now show all tools available
```

---

## Usage

### Run predictions

```bash
# Single query
nanobot-bio agent --message "Does RNA GGCGGAGGAGGAGGA interact with RBP PTBP1?"

# Streaming output (slower, but real-time)
nanobot-bio chat --message "Does RNA GGCGGAGGAGGAGGA interact with RBP PTBP1?"

# From file
nanobot-bio agent --message "$(cat query.txt)"
```

### Verify environment setup

```bash
nanobot-bio doctor
# Output:
#   ✅ Python 3.10.5
#   ✅ DELIVERY_ROOT: /data/rhobind_agent_delivery
#   ✅ NANOBOT_SRC: nanobot (pip)
#   ✅ Registry: 42 tools available
#   ⚠️  AF3: deferred (set AF3_CKPT to enable)
```

### Run tests

```bash
# All tests
pytest tests/

# Fast compliance check
pytest tests/test_proposal_compliance.py -q

# With coverage
pytest tests/ --cov=app --cov=rbp_eval --cov-report=html
```

### Advanced commands (maintainers)

| Command | Purpose |
|---------|---------|
| `nanobot-bio accept-golden` | Authoritative acceptance test (requires GPU) |
| `nanobot-bio accept-llm` | LLM-based verdict validation |
| `nanobot-bio eval-plan` | Ablation study & metrics protocol |
| `nanobot-bio layout` / `gate` | SoT validation + engineering checks |

---

## Output Format

### Typical verdict JSON

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

### Interpreting results

- **Confidence = "Strong"** → p_hat ≥ 0.75 & strong evidence → **Trust this prediction**
- **Confidence = "Likely"** → p_hat ≥ 0.50 & moderate evidence → **Likely binding**
- **Confidence = "Unlikely"** → p_hat < 0.50 → **Probably no binding**
- **Confidence = "No"** → p_hat < 0.25 → **No binding**

**Caveats to watch for:**
- `low_head_coverage` → Predictor uncertain (few donors)
- `structure_axis_unavailable` → AF3 failed (use AFDB instead)
- `domain_empty` → No domain annotation found
- `af3_fallback_used` → AFDB unavailable, AF3 used instead

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
# Check where nanobot is installed
python -c "import nanobot; print(nanobot.__file__)"

# If pip version is outdated, use local clone
export NANOBOT_SRC=~/git/nanobot
nanobot-bio doctor
```

### Q4: AF3 weights download stuck

**Error:**
```
Timeout downloading AF3 weights (100+ GB)
```

**Solutions:**
- Ensure stable internet & plenty of disk space (150GB)
- Skip for now: `bash scripts/setup_all.sh --skip-af3`
- Resume later: `python -m app.models.af3_setup --resume`

### Q5: LLM API errors

**Error:**
```
AuthenticationError: Invalid API key
```

**Fix:**
```bash
nanobot-bio onboard  # Reconfigure API key
# or export manually:
export OPENAI_API_KEY=sk-...
```

---

## Known Limitations

- **Light LOO evaluation** uses CSV lookup; full FASTA recompute deferred
- **Label calibration** requires ground-truth `{p_hat, y}` pairs (not all datasets available)
- **AF3 fallback** adds significant latency (30–60 min per RNA with GPU)
- **Delivery v2 score calibration** is NOT available in this version (Delivery team only)
- **Parallel retrieve** is hardware-dependent; some GPUs may hit memory limits with 4 parallel tools
- **No batch inference** (single RNA per query; loop in shell for multiple queries)

---

## Configuration

Edit [`config/defaults.yaml`](config/defaults.yaml) to customize:

```yaml
# Number of candidate donors
n_cand: 5

# Similarity fusion axes
axes:
  structure: true       # Use structural similarity
  rna_blastn: true      # Use RNA sequence similarity
  literature: true      # Use literature knowledge

# AF3 fallback (when AFDB fails)
structure_policy:
  use_af3: false
  use_af3_fallback: true

# Confidence thresholds
label_thresholds:
  strong: 0.75
  likely: 0.50
  unlikely: 0.25
```

---

## Contributing

We welcome bug reports, feature requests, and pull requests!

### Report a bug or request a feature

Open an [issue](https://github.com/JoeSun-421/rbp-nanobot-bio/issues) with:
- Clear description of the problem
- Steps to reproduce (or expected vs. actual output)
- Environment info (Python version, GPU, OS)

### Submit a pull request

1. Fork this repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests: `pytest tests/`
4. Push and open a PR

**Code style:**
- Run `ruff check .` before committing
- Format with `ruff format .`
- All tests must pass: `pytest tests/ -q`

---

## Testing

```bash
# Full test suite
pytest tests/

# Specific test file
pytest tests/test_proposal_compliance.py -v

# Fast smoke test
pytest tests/ -k "not gpu" --co  # Just list tests
```

---

## Resources

- **[Nanobot Framework](https://github.com/HKUDS/nanobot)** — Agent orchestration engine
- **[Full Proposal](docs/proposal.md)** — Scientific specification (Table 2–3)
- **[Engineering Guide](docs/工程指南.zh.md)** — Development workflow & gates
- **[Changelog](CHANGELOG.md)** — Release notes & version history
- **[Issues](https://github.com/JoeSun-421/rbp-nanobot-bio/issues)** — Bug reports & feature requests
- **[Discussions](https://github.com/JoeSun-421/rbp-nanobot-bio/discussions)** — Q&A & general discussion

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
- [rhobind_agent_delivery](https://github.com/HKUDS/rhobind_agent_delivery) team for the predictor & databases
- All contributors and users for feedback & improvements
