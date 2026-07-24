<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="480">

  <h1>nanobot-bio</h1>

  <p><b>RNA–RBP interaction prediction agent</b></p>
  <p>
    Ask whether an RNA binds an RBP.<br/>
    Built on <a href="https://github.com/HKUDS/nanobot">Nanobot</a> · scores from a science tool bundle via a read-only bridge.
  </p>

  <p>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p>
    <a href="#-idea">Idea</a> ·
    <a href="#-clone">Clone</a> ·
    <a href="#-install">Install</a> ·
    <a href="#-run">Run</a> ·
    <a href="#-what-you-get">What you get</a> ·
    <a href="#-layout">Layout</a> ·
    <a href="#-more-help">Help</a>
  </p>

  <p><b>English</b> · <a href="README.zh.md">中文</a></p>
</div>

---

## 🔬 Idea

**Biology.** Many RNA-binding proteins (RBPs) recognize RNA through related sequence motifs, folds, and domains. If a query RBP is close to proteins we already know how to score, we can **transfer** that knowledge: find similar donors, reuse their predictors, then combine evidence into one binding call.

**What we built.** `nanobot-bio` is the agent that does this end to end:

1. **Resolve** the target RBP and decide the path — known panel head, near-homolog, or fully unseen.
2. **Retrieve** similar RBPs with sequence and structure signals.
3. **Predict** binding with the science stack on the right donors.
4. **Integrate** donor scores into a single JSON verdict with a short explanation.

The LLM plans which tools to call and writes the explanation. **Numeric scores always come from the science tools**, not from the model inventing probabilities.

---

## 📦 Clone

| Command | Meaning |
|---------|---------|
| `git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git` | Download this project from GitHub over HTTPS |
| `cd rbp-nanobot-bio` | Enter the project folder |

Place the science bundle **next to** this repo:

```text
your_workspace/
├── rbp-nanobot-bio/            ← this project
└── rhobind_agent_delivery/     ← science data & tools
```

---

## ⚙️ Install

| Command | Meaning |
|---------|---------|
| `bash scripts/setup_all.sh` | Create the Python environment, install dependencies, wire paths to the science bundle |
| `source .venv/bin/activate` | Activate that environment so `nanobot-bio` is on your PATH |
| `nanobot-bio onboard` | Interactive setup: pick an LLM provider and save your API key locally |
| `nanobot-bio doctor` | Self-check: delivery paths, registry, skill sync, and basic readiness |

Need a lighter install, Docker, or the full env table? See [`INSTALL.md`](INSTALL.md).

---

## 🚀 Run

| Command | Meaning |
|---------|---------|
| `nanobot-bio agent --message "..."` | One-shot run: send one question, get one JSON verdict, then exit |
| `nanobot-bio chat` | Multi-turn terminal chat with the same agent |

Example:

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <your_sequence>"
nanobot-bio chat
```

### Chat slash commands

| Command | Meaning |
|---------|---------|
| `/help` | Show available slash commands |
| `/status` | Show current model, tools, and session |
| `/tools` | List tools the agent can call |
| `/new` | Start a fresh session |
| `/quit` | Leave chat |

---

## ✨ What you get

| Piece | Role |
|-------|------|
| **Agent** | Plans tool calls and returns a JSON answer |
| **Tools** | Sequence / structure / function lookup & prediction |
| **Science stack** | Binding scores from `rhobind_agent_delivery` |

Typical answer fields: `label`, `confidence`, `p_hat`, `explanation`, `supporting_rbps`.

---

## 📁 Layout

```text
nanobot-bio/
├── app/          CLI & app shell
├── nanobot/      Agent runtime + RBP tools
├── config/       Default settings
├── scripts/      setup_all.sh
├── tests/        Automated tests
├── workspace/    Agent workspace
└── artifacts/    Local logs & reports
```

---

## 🆘 More help

| Doc | When to open it |
|-----|-----------------|
| [INSTALL.md](INSTALL.md) | Full setup, env vars, Docker |
| [CHANGELOG.md](CHANGELOG.md) | What changed by version |
| [RELEASE.md](RELEASE.md) | Cutting a release |

```bash
nanobot-bio doctor          # self-check when something looks wrong
python -m pytest -q         # run the automated test suite quietly
```

---

<div align="center">

Agent runtime derived from <a href="https://github.com/HKUDS/nanobot">HKUDS/nanobot</a>.<br/>
Science tools provided by <code>rhobind_agent_delivery</code>.

</div>
