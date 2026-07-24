<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="420">

  <h1>nanobot-bio</h1>
  <p>RNA–RBP interaction prediction agent</p>

  <p>
    <a href="https://github.com/JoeSun-421/rbp-nanobot-bio/stargazers"><img src="https://img.shields.io/github/stars/JoeSun-421/rbp-nanobot-bio?style=flat" alt="Stars"></a>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python ≥3.10">
    <img src="https://img.shields.io/badge/version-0.5.1-green" alt="Version">
    <a href="https://github.com/JoeSun-421/rbp-nanobot-bio/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/JoeSun-421/rbp-nanobot-bio/ci.yml?branch=main&label=CI" alt="CI"></a>
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p><b>English</b> · <a href="README.zh.md">中文</a></p>
</div>

## What this is

nanobot-bio is a command-line agent that estimates whether an RNA is likely to bind an RBP (RNA-binding protein), and roughly how strongly.

This repository is the **agent layer** (CLI, tool orchestration, chat, verdict shape). Numeric predictors, the RBP registry, embedding / structure indexes, and RhoBind checkpoints live in the sibling science bundle **`rhobind_agent_delivery`**. The agent calls that stack through a read-only bridge. The LLM picks tools, follows stage rules, and writes explanations — it does **not** invent `p_hat`.

```text
User question
  → nanobot-bio CLI (agent / chat)
  → in-repo Nanobot runtime + RBP toolkit
  → read-only science bridge
  → rhobind_agent_delivery (scoring & retrieval)
  → JSON verdict
```

Typical uses: interactive queries after a local delivery install, collaborator bring-up, and regression on fixed own-head / LLM touchpoint checks.

### Verdict fields

| Field | Meaning |
|-------|---------|
| `label` | Binding label (e.g. Strong / Likely / Unlikely) from `p_hat` and thresholds |
| `confidence` | Confidence in this run (may be low or abstain when evidence is weak) |
| `p_hat` | Binding probability estimate from predict tools only |
| `explanation` | Short rationale (often LLM-written on top of tool results) |
| `supporting_rbps` | RBPs / donors supporting the call |

Default label cuts (`config/defaults.yaml`, overridable):

| Condition | Label tendency |
|-----------|----------------|
| `p_hat ≥ 0.75` | Strong |
| `p_hat ≥ 0.50` | Likely |
| `p_hat ≥ 0.25` | Unlikely |
| Lower | Farther from binding (see config / normalize logic) |

Example:

```json
{
  "label": "Strong",
  "confidence": "high",
  "p_hat": 0.966,
  "explanation": "...",
  "supporting_rbps": ["PTBP1"]
}
```

## Requirements

| Item | Notes |
|------|--------|
| OS | Linux x86_64 recommended; validated on Ubuntu 20.04+. macOS / WSL may run the agent layer; full science stack is not fully validated there |
| Python | ≥ 3.10 (3.13 recommended) |
| Disk | Plan ≥ 30 GB free for a full science stack (delivery + conda) |
| GPU | Optional; helps predict / ESM / AF3. CPU is enough for `doctor` and light chat |
| Delivery | `rhobind_agent_delivery` next to this repo (same parent directory) |
| LLM | OpenAI-compatible API key via `onboard` |

Obtain the delivery bundle separately (collaborator copy, or rebuild per delivery docs). Details: [INSTALL.md](INSTALL.md).

## Install

```bash
# Parent directory should contain:
#   rbp-nanobot-bio/          (this repo)
#   rhobind_agent_delivery/   (science bundle)

git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

bash scripts/setup_all.sh                 # agent venv + conda science envs
# bash scripts/setup_all.sh --skip-conda  # agent layer only

source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
```

Notes:

- Do not `pip install nanobot-ai` — it steals `import nanobot` from the in-repo slim copy.
- `setup_all.sh` uses in-repo `nanobot/`; it does not clone a sibling Nanobot tree.
- Docker: `docker compose build` (agent-only) or `docker compose --profile full build`. See [INSTALL.md](INSTALL.md).

## Usage

### Day-to-day commands

| Command | Description |
|---------|-------------|
| `nanobot-bio onboard` | LLM provider, API key, model |
| `nanobot-bio doctor` | Paths, registry, axes, readiness |
| `nanobot-bio agent --message "..."` | One-shot question → verdict |
| `nanobot-bio chat` | Multi-turn chat |

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: AUCG..."
nanobot-bio chat
```

Chat slash commands: `/help` · `/status` · `/tools` · `/new` · `/quit`.

A useful question usually includes:

1. **RBP name** (e.g. PTBP1)
2. **RNA sequence**, or an explicit pointer to file / pasted contents
3. Optional context (cohort, panel-only, etc.)

The agent starts with `resolve_rbp`, then branches on in-panel vs unseen.

### Example prompts

```text
Does this RNA interact with RBP PTBP1?
RNA: GGUCU... (full sequence)

Will this RNA bind PTBP1? Sequence: ...

Query RBP is off-panel. RNA: ... ; protein sequence / UniProt: ...
```

In multi-turn chat you can ask follow-ups (“why Likely?”, “which supporting_rbps?”). For a new RNA, paste the sequence again so the referent stays clear.

### Routing

**In-panel (own head)**

1. `resolve_rbp` → `in_panel=true`
2. Call `predict_interaction` once (own head)
3. Map `predictions[0].prob` → `p_hat` / `label`
4. Emit JSON verdict and stop  
   No transfer, similarity retrieval, domain / literature extras on this path.

**Unseen target (no own head)**

1. Multi-axis retrieval of **donors** (embedding, sequence, domain, structure, … — gated by `axes` in `config/defaults.yaml`)
2. `predict_interaction` on donor heads
3. Fuse with similarity / abstain rules (`integrate` / `abstain_thresholds`)
4. One verdict; `p_hat` still only from predict tools

Known check: delivery sample positive RNA × **PTBP1** → own-head ≈ **0.966**.

### Acceptance and engineering commands (optional)

| Command | Description |
|---------|-------------|
| `nanobot-bio accept-golden` | Own-head golden (no LLM; PTBP1 × positive RNA) |
| `nanobot-bio accept-llm` | LLM touchpoint accept (needs API key) |
| `nanobot-bio gap-closure` | Stage-0 / unseen evidence report |
| `nanobot-bio gate` | ruff + pytest + layout engineering gate |

Reports usually land under `artifacts/reports/`. Public CI runs a light `test` job; science jobs need a self-hosted runner — see [INSTALL.md](INSTALL.md) and [RELEASE.md](RELEASE.md).

Local tests:

```bash
python -m pytest -q
```

## Configuration

Primary file: `config/defaults.yaml`.

| Block | Role |
|-------|------|
| `top_k` / `n_cand` | Retrieval and candidate sizes |
| `axes.*` | Enable embedding, sequence, domain, structure, AF3, literature, … |
| `fusion_weights` | Multi-signal fusion weights |
| `label_thresholds` | `p_hat` → label |
| `abstain_thresholds` | Abstain when similarity is too low |
| `integrate` | Transfer prior, donor quality, abstain switch |
| `llm.*` | LLM touchpoints (function reasoning / final explanation) |

LLM credentials: `nanobot-bio onboard` → typically `~/.nanobot/config.json` (`chmod 600` recommended). Override path with `NANOBOT_CONFIG`. **Do not commit keys.**

| Variable | Purpose |
|----------|---------|
| `BIO_ROOT` | Shared parent of this repo and delivery |
| `DELIVERY_ROOT` | Root of `rhobind_agent_delivery` |
| `NANOBOT_BIO_ROOT` | This repository root |
| `NANOBOT_WORKSPACE` | Agent workspace (default `workspace/`) |
| `NANOBOT_CONFIG` | LLM config file |
| `RHOBIND_DEVICE` | `auto` / `cuda` / `cpu` |
| `AGENT_DB` | Registry, embeddings, and related DBs |

Full env table and Docker volumes: [INSTALL.md](INSTALL.md). Stage rules: [AGENTS.md](AGENTS.md) and `workspace/AGENTS.md`.

## Limits

- Without delivery you only get the agent shell; real scoring is unavailable.
- Predictions depend on panel / donor coverage and model quality — **not** a wet-lab substitute.
- AF3 may be deferred or fail without AFDB; failures become caveats while other axes continue (see INSTALL FAQ).
- If `docs/` exists locally, it is kept local and is not pushed with the public tree by default.

## Related docs

| Doc | Content |
|-----|---------|
| [INSTALL.md](INSTALL.md) | Install paths, env vars, Docker, acceptance |
| [AGENTS.md](AGENTS.md) | Agent stage constraints |
| [RELEASE.md](RELEASE.md) | Release and CI runners |
| [VENDOR.md](VENDOR.md) | In-repo slim Nanobot notes |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## License

MIT.

## Acknowledgements

- Runtime based on [HKUDS/nanobot](https://github.com/HKUDS/nanobot)
- Predictors and data from `rhobind_agent_delivery`
- Maintainer: [JoeSun-421](https://github.com/JoeSun-421)
