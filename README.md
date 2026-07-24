<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="480">

  <h1>nanobot-bio</h1>
  <p><b>RNA–RBP Interaction Prediction Agent</b></p>
  <p>Ask whether an RNA binds an RBP — and how strongly — through a tool-grounded agent.</p>

  <p>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python ≥3.10">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="https://github.com/JoeSun-421/rbp-nanobot-bio/actions"><img src="https://img.shields.io/github/actions/workflow/status/JoeSun-421/rbp-nanobot-bio/ci.yml?branch=main&label=CI" alt="CI"></a>
  </p>

  <p>
    <a href="#english">English</a> ·
    <a href="#chinese">中文</a>
  </p>
</div>

---

<a id="english"></a>

# English

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Demo](#demo)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Tech Stack](#tech-stack)
- [Project Layout](#project-layout)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Overview

**nanobot-bio** is a command-line agent for **RNA–RBP** (RNA-binding protein) interaction prediction.

Many RBPs share related sequence and structural patterns. When a query protein resembles ones we can already score, the agent finds those neighbors (**donors**), reuses their predictors, and combines evidence into one binding decision.

You ask in natural language. The agent plans tool calls, runs scientific scoring through a dedicated tool bundle, and returns a structured JSON **verdict**.

> Binding scores come from the science toolkit (`rhobind_agent_delivery`), not from the LLM inventing numbers. The model plans steps and writes explanations.

## Features

- **End-to-end Q&A** — one-shot `agent` or multi-turn `chat`
- **Homology-aware routing** — known panel heads, near-homologs, or unseen targets
- **Multi-signal retrieval** — sequence and structure similarity to find donor RBPs
- **Tool-grounded scores** — predictions from the science stack behind a read-only bridge
- **Structured output** — JSON with `label`, `confidence`, `p_hat`, `explanation`, `supporting_rbps`
- **Local setup helpers** — `onboard` for LLM keys, `doctor` for environment checks

## Demo

> **Screenshot / recording placeholder**  
> Suggested: a short terminal capture of `nanobot-bio chat` answering a PTBP1 question, plus a sample JSON verdict.  
> Place media under `assets/` (e.g. `assets/demo.gif`) and embed here.

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: AUCG..."
```

Example verdict shape:

```json
{
  "label": "Likely",
  "confidence": "medium",
  "p_hat": 0.72,
  "explanation": "...",
  "supporting_rbps": ["..."]
}
```

## Quick Start

### Prerequisites

- Linux x86_64 recommended  
- Python ≥ 3.10  
- Science bundle `rhobind_agent_delivery` placed **next to** this repository  
- An LLM API key (OpenAI-compatible providers supported via onboard)

```text
your_workspace/
├── rbp-nanobot-bio/             ← this repo
└── rhobind_agent_delivery/      ← science data & tools
```

### Install & run

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

bash scripts/setup_all.sh      # create venv, install deps, wire paths
source .venv/bin/activate
nanobot-bio onboard            # LLM provider + API key
nanobot-bio doctor             # verify paths & readiness
nanobot-bio chat               # start interactive session
```

For Docker, lighter installs, and the full environment variable table, see [`INSTALL.md`](INSTALL.md).

## Usage

| Command | Description |
|---------|-------------|
| `nanobot-bio onboard` | Configure LLM provider and API key |
| `nanobot-bio doctor` | Check delivery paths and local readiness |
| `nanobot-bio agent --message "..."` | One-shot prediction |
| `nanobot-bio chat` | Multi-turn terminal chat |

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <sequence>"
nanobot-bio chat
```

Chat slash commands: `/help` · `/status` · `/tools` · `/new` · `/quit`

## Architecture

```text
User
  │
  ▼
nanobot-bio CLI  (agent / chat)
  │
  ├─ Agent runtime (Nanobot)     plan tools, explain results
  ├─ RBP toolkit                 sequence / structure / function / integrate
  └─ Science bridge              call rhobind_agent_delivery (read-only)
           │
           ▼
     Binding scores & evidence
           │
           ▼
     JSON verdict
```

| Layer | Role |
|-------|------|
| **Agent** | Plans which tools to call and formats the answer |
| **Toolkit** | RBP retrieval and prediction tool interfaces |
| **Science stack** | Authoritative numeric scores from `rhobind_agent_delivery` |

## Configuration

Primary knobs live in `config/defaults.yaml` (candidate sizes, similarity cutoffs, label thresholds, axes).

LLM credentials are stored locally via `nanobot-bio onboard` (typically `~/.nanobot/config.json`). **Do not commit API keys.**

Common environment variables:

| Variable | Purpose |
|----------|---------|
| `BIO_ROOT` | Parent directory of this repo and the science bundle |
| `DELIVERY_ROOT` | Path to `rhobind_agent_delivery` |
| `NANOBOT_BIO_ROOT` | This repository root |
| `NANOBOT_CONFIG` | LLM config file path |

Details: [`INSTALL.md`](INSTALL.md).

## Tech Stack

| Area | Stack |
|------|--------|
| Language | Python ≥ 3.10 |
| Agent runtime | [Nanobot](https://github.com/HKUDS/nanobot) (slim in-repo) |
| CLI / UX | argparse, prompt_toolkit, Rich |
| Science scoring | `rhobind_agent_delivery` (conda-isolated tools) |
| Config | YAML (`config/defaults.yaml`) |
| Tests | pytest |

## Project Layout

```text
nanobot-bio/
├── app/           CLI and application shell
├── nanobot/       Agent runtime + RBP tools
├── config/        Default settings
├── scripts/       setup_all.sh and helpers
├── tests/         Automated tests
├── workspace/     Agent workspace
├── artifacts/     Local logs & reports (gitignored)
└── INSTALL.md     Full installation guide
```

## Roadmap

- [x] CLI agent / chat for RNA–RBP questions  
- [x] Tool-grounded scoring via science bundle  
- [x] Local onboard + doctor checks  
- [ ] Richer demo assets (GIF / sample sessions)  
- [ ] Broader provider presets and docs for collaborators  
- [ ] Optional packaged release artifacts *(planned)*  

> Items marked *planned* may change with evaluation results.

## Contributing

Issues and PRs are welcome.

1. Fork the repo and create a feature branch  
2. Keep changes focused; run `python -m pytest -q` before opening a PR  
3. Do not commit secrets (`.env`, API keys, local configs)  
4. For install / env questions, prefer updating `INSTALL.md` over expanding the README  

## License

MIT — see the repository license file.

## Acknowledgements

- Agent runtime based on [HKUDS/nanobot](https://github.com/HKUDS/nanobot)  
- Scientific predictors and databases from `rhobind_agent_delivery`  
- Maintainer: [JoeSun-421](https://github.com/JoeSun-421)

---

<a id="chinese"></a>

# 中文

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [演示](#演示)
- [快速开始](#快速开始)
- [使用方式](#使用方式)
- [架构](#架构)
- [配置说明](#配置说明)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [路线图](#路线图)
- [贡献指南](#贡献指南)
- [许可证](#许可证)
- [致谢](#致谢)

## 项目简介

**nanobot-bio** 是一个面向 **RNA–RBP**（RNA-binding protein，RNA 结合蛋白）相互作用预测的命令行 Agent。

许多 RBP 在序列与结构上彼此相近。当查询蛋白与已有可打分的蛋白相似时，Agent 会寻找这些邻居（**donors**，供体），复用其预测能力，并把证据汇总成一次结合判定。

你用自然语言提问；Agent 规划工具调用，通过独立科学工具包完成打分，并返回结构化的 JSON **verdict**（判定结果）。

> 结合分数来自科学工具包（`rhobind_agent_delivery`），不是由 LLM 编造数值。模型负责规划步骤与撰写解释。

## 功能特性

- **端到端问答** — 支持一次性 `agent` 与多轮 `chat`
- **同源感知路径** — 覆盖目录内已知 head、近同源与未见靶标
- **多信号检索** — 结合序列与结构相似度寻找供体 RBP
- **工具落地打分** — 经只读 bridge 调用科学栈得到预测分数
- **结构化输出** — JSON 字段含 `label`、`confidence`、`p_hat`、`explanation`、`supporting_rbps`
- **本地辅助命令** — `onboard` 配置密钥，`doctor` 检查环境

## 演示

> **截图 / 录屏占位**  
> 建议：`nanobot-bio chat` 询问 PTBP1 的终端录屏，以及一份示例 JSON verdict。  
> 可将素材放在 `assets/`（如 `assets/demo.gif`）并在此嵌入。

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: AUCG..."
```

输出形态示例：

```json
{
  "label": "Likely",
  "confidence": "medium",
  "p_hat": 0.72,
  "explanation": "...",
  "supporting_rbps": ["..."]
}
```

## 快速开始

### 环境要求

- 推荐 Linux x86_64  
- Python ≥ 3.10  
- 科学工具包 `rhobind_agent_delivery` 与本仓库**同级**放置  
- LLM API key（可通过 onboard 配置 OpenAI 兼容厂商）

```text
你的工作目录/
├── rbp-nanobot-bio/             ← 本仓库
└── rhobind_agent_delivery/      ← 科学数据与工具
```

### 安装与运行

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

bash scripts/setup_all.sh      # 创建虚拟环境、安装依赖、接好路径
source .venv/bin/activate
nanobot-bio onboard            # 配置 LLM 与 API key
nanobot-bio doctor             # 检查路径与就绪状态
nanobot-bio chat               # 进入交互对话
```

Docker、精简安装与完整环境变量表见 [`INSTALL.md`](INSTALL.md)。

## 使用方式

| 命令 | 说明 |
|------|------|
| `nanobot-bio onboard` | 配置 LLM 厂商与 API key |
| `nanobot-bio doctor` | 检查科学包路径与本地就绪情况 |
| `nanobot-bio agent --message "..."` | 一次性预测 |
| `nanobot-bio chat` | 多轮终端对话 |

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <sequence>"
nanobot-bio chat
```

对话斜杠命令：`/help` · `/status` · `/tools` · `/new` · `/quit`

## 架构

```text
用户
  │
  ▼
nanobot-bio CLI  (agent / chat)
  │
  ├─ Agent runtime (Nanobot)     规划工具、解释结果
  ├─ RBP toolkit                 序列 / 结构 / 功能 / 整合
  └─ Science bridge              只读调用 rhobind_agent_delivery
           │
           ▼
     结合分数与证据
           │
           ▼
     JSON verdict
```

| 层 | 职责 |
|----|------|
| **Agent** | 决定调用哪些工具，并组织最终回答 |
| **Toolkit** | RBP 检索与预测的工具接口 |
| **Science stack** | 来自 `rhobind_agent_delivery` 的权威数值分数 |

## 配置说明

主要参数在 `config/defaults.yaml`（候选数量、相似度阈值、标签切分、各轴开关等）。

LLM 凭证由 `nanobot-bio onboard` 写入本机（通常为 `~/.nanobot/config.json`）。**请勿将 API key 提交进仓库。**

常用环境变量：

| 变量 | 用途 |
|------|------|
| `BIO_ROOT` | 本仓库与科学工具包的共同父目录 |
| `DELIVERY_ROOT` | `rhobind_agent_delivery` 路径 |
| `NANOBOT_BIO_ROOT` | 本仓库根目录 |
| `NANOBOT_CONFIG` | LLM 配置文件路径 |

更多说明见 [`INSTALL.md`](INSTALL.md)。

## 技术栈

| 领域 | 技术 |
|------|------|
| 语言 | Python ≥ 3.10 |
| Agent runtime | [Nanobot](https://github.com/HKUDS/nanobot)（仓内精简版本） |
| CLI / UX | argparse、prompt_toolkit、Rich |
| 科学打分 | `rhobind_agent_delivery`（conda 隔离工具） |
| 配置 | YAML（`config/defaults.yaml`） |
| 测试 | pytest |

## 目录结构

```text
nanobot-bio/
├── app/           命令行与应用壳
├── nanobot/       Agent runtime + RBP 工具
├── config/        默认配置
├── scripts/       setup_all.sh 等脚本
├── tests/         自动化测试
├── workspace/     Agent 工作区
├── artifacts/     本地日志与报告（gitignore）
└── INSTALL.md     完整安装指南
```

## 路线图

- [x] RNA–RBP 问答 CLI（agent / chat）  
- [x] 经科学工具包落地打分  
- [x] 本地 onboard + doctor  
- [ ] 更完整的演示素材（GIF / 示例会话）  
- [ ] 更丰富的厂商预设与协作者文档  
- [ ] 可选的打包发布产物 *（计划中）*  

> 标注为「计划中」的条目可能随评测结果调整。

## 贡献指南

欢迎提交 Issue 与 Pull Request。

1. Fork 仓库并创建功能分支  
2. 改动尽量聚焦；提 PR 前运行 `python -m pytest -q`  
3. 不要提交密钥（`.env`、API key、本机配置）  
4. 安装 / 环境类说明优先更新 `INSTALL.md`，避免 README 膨胀  

## 许可证

MIT — 详见仓库中的 license 文件。

## 致谢

- Agent runtime 基于 [HKUDS/nanobot](https://github.com/HKUDS/nanobot)  
- 科学预测与数据来自 `rhobind_agent_delivery`  
- 维护者：[JoeSun-421](https://github.com/JoeSun-421)
