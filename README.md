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

## Overview

nanobot-bio is a command-line agent for estimating whether an RNA binds an RBP (RNA-binding protein), and roughly how strongly.

This repo is the agent layer (CLI, tools, chat, verdict). Numeric scores come from the sibling science bundle `rhobind_agent_delivery` via a read-only bridge. The LLM plans tool calls and writes explanations; it does not invent `p_hat`.

Output is a JSON verdict (`label`, `confidence`, `p_hat`, `explanation`, `supporting_rbps`).

- **In-panel RBP** — `resolve_rbp` → one `predict_interaction` (own head) → verdict.
- **Unseen RBP** — retrieve donor RBPs → predict on their heads → integrate → verdict.

Install detail, env vars, Docker, and acceptance: [INSTALL.md](INSTALL.md).

## Quick Start

Requirements: Linux x86_64 recommended, Python ≥ 3.10, `rhobind_agent_delivery` next to this repo, LLM API key.

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

bash scripts/setup_all.sh
source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
nanobot-bio chat
```

Do not `pip install nanobot-ai` (conflicts with the in-repo `nanobot/`). Agent-only setup: `bash scripts/setup_all.sh --skip-conda`.

## Usage

| Command | Description |
|---------|-------------|
| `nanobot-bio onboard` | Configure LLM provider and API key |
| `nanobot-bio doctor` | Check paths and readiness |
| `nanobot-bio agent --message "..."` | One-shot prediction |
| `nanobot-bio chat` | Multi-turn chat |

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <sequence>"
nanobot-bio chat
```

In chat: `/help` · `/status` · `/tools` · `/new` · `/quit`. Include the RBP name and RNA sequence in the question.

Example verdict:

```json
{
  "label": "Strong",
  "confidence": "high",
  "p_hat": 0.966,
  "explanation": "...",
  "supporting_rbps": ["PTBP1"]
}
```
