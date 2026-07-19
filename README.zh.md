# nanobot-bio

[![Python](https://img.shields.io/badge/python-≥3.10-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-see%20repo-lightgrey.svg)](#许可与归属)
[![Release](https://img.shields.io/badge/release-v0.2.0-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

[English](README.md) | **中文**

面向 **RNA–RBP 相互作用**判定的 LLM 智能体。产品路径是真正的工具调用 agent（`Nanobot.run` + skills + delivery 桥接），不是固定流水线。

> **范围。** 本仓库仅包含 **agent 产品包**。科学工具、checkpoint 与数据库在旁路 delivery 包（`rhobind_agent_delivery/`，运行时只读）中，**不**随本仓库分发。

---

## 目录

- [功能](#功能)
- [架构](#架构)
- [仓库结构](#仓库结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [CLI](#cli)
- [行为约束](#行为约束)
- [配置](#配置)
- [版本](#版本)
- [安全](#安全)
- [许可与归属](#许可与归属)

---

## 功能

| 能力 | 说明 |
|------|------|
| Stage-0 own-head | 目录内 RBP → resolve → predict → 结构化 JSON |
| Transfer | 未见 RBP → 检索 donor → 预测 → integrate |
| 多厂商 LLM | OpenAI、Anthropic、DeepSeek、Gemini、通义、智谱、Moonshot 等 |
| 科学桥接 | Conda 隔离的 delivery 工具（ESM、Foldseek、RhoBind、可选 AF3） |
| 安全默认 | 禁止编造 `p_hat`；agent 路径禁用 shell / web_search |

---

## 架构

```text
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────────┐
│  rbp-agent (CLI)    │────▶│  Nanobot 运行时       │────▶│  rhobind_agent_delivery │
│  onboard / chat /   │     │  （旁路安装）         │     │  （只读科学包）          │
│  doctor / agent     │     │  + §6.2 RBP 工具      │     │  conda 环境 + 脚本      │
└─────────────────────┘     └──────────────────────┘     └─────────────────────────┘
```

| 路径 | 适用 | 流程 |
|------|------|------|
| Stage 0 | 目录内 RBP | `resolve_rbp` → `predict_interaction` → JSON → **停止** |
| Transfer | 未见 / 强制 | 检索 → donor 预测 → integrate → JSON |

---

## 仓库结构

本仓库在 `nanobot/` 下只保留提案 **§6.2 覆盖层**（skills + `tools/rbp`），作为同步用的 SoT，不是可 import 的完整框架。完整 nanobot 作为旁路运行时。

```text
nanobot-bio/                   # 本 git 仓库
├── nanobot/                   # §6.2 SoT — skills + agent/tools/rbp
├── backends/delivery/         # 桥接 delivery 脚本（conda 环境）
├── core/                      # onboard / chat UX / verdict schema
├── rbp_eval/                  # traces 与评测辅助
├── scripts/                   # setup_all、activate_env、同步脚本
├── cli.py                     # rbp-agent 入口
└── integrate.py               # RBPAgent → Nanobot.from_config().run
```

期望的旁路布局（不在本仓库内）：

```text
<workspace>/
├── nanobot/                   ← 运行时；import nanobot → 这里
├── nanobot-bio/               ← 本包
└── rhobind_agent_delivery/    ← 科学包（设置 DELIVERY_ROOT）
```

结构检查：

```bash
python scripts/check_proposal_62_layout.py
```

---

## 环境要求

- Python ≥ 3.10（agent venv）
- Delivery 提供的 conda 环境：`protein_embed`、`rna`、`rhobind`（AF3 可选）
- **推荐：** CUDA GPU + 足够内存（RhoBind / ESM）
- 通过 `rbp-agent onboard` 配置 LLM（写入本机 `~/.nanobot/config.json`——**勿提交**）
- ESM 等 Hugging Face 权重（本地缓存；可用 `HF_ENDPOINT` 镜像）

---

## 快速开始

```bash
export BIO_ROOT=/path/to/workspace
export DELIVERY_ROOT=$BIO_ROOT/rhobind_agent_delivery

# 首次一次：agent venv + 科学 conda
bash $BIO_ROOT/nanobot-bio/scripts/setup_all.sh
# 仅 agent（跳过科学 conda）：加 --skip-conda

# 日常：轻量激活
source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh

rbp-agent onboard
rbp-agent doctor
rbp-agent chat
rbp-agent agent --example pos --strict
```

可用 `NANOBOT_GIT`、`NANOBOT_SRC` 覆盖 nanobot 路径。  
拉取代码后重同步覆盖层：`ACTIVATE_HEAVY=1 source …/activate_env.sh`。

---

## CLI

| 命令 | 用途 |
|------|------|
| `rbp-agent onboard` | 配置 LLM 厂商 / 模型 / API key |
| `rbp-agent doctor` | 检查 delivery 与 conda |
| `rbp-agent chat` | 交互式会话 |
| `rbp-agent agent` | 单次运行 |
| `rbp-agent own-head` | Own-head 冒烟（无需 LLM） |
| `rbp-agent predict` | 直接调用 predict API |

---

## 行为约束

- 产品路径仅为 **`Nanobot.run`**
- **禁止编造 `p_hat`**；预测 OOM/超时 → `p_hat=null`，勿重试
- Stage 0 在成功 own-head 后必须停止
- delivery 只读，仅通过桥接调用
- 禁用 shell / `web_search` / `web_fetch`；文献用 `literature_search`

---

## 配置

| 变量 | 作用 |
|------|------|
| `BIO_ROOT` | 工作区根目录 |
| `DELIVERY_ROOT` | delivery 路径 |
| `NANOBOT_SRC` | 旁路 nanobot 运行时 |
| `NANOBOT_WORKSPACE` | agent workspace |
| `NANOBOT_CONFIG` | LLM 配置（默认 `~/.nanobot/config.json`） |
| `RHOBIND_DEVICE` | `auto` / `cuda` / `cpu` |
| `CONDA_ENVS_PATH` | 非标准 conda envs 目录时设置 |
| `HF_HOME` / `HF_ENDPOINT` | HF 缓存与可选镜像 |

复制 [`.env.example`](.env.example) → `.env`（已被 gitignore）。

---

## 版本

| 版本 | 说明 |
|------|------|
| [v0.1.0](https://github.com/JoeSun-421/rbp-nanobot-bio/releases/tag/v0.1.0) | 首次推送到 GitHub 的 agent 包 |
| [v0.2.0](https://github.com/JoeSun-421/rbp-nanobot-bio/releases/tag/v0.2.0) | §6.2 外部化、delivery 客户端加固、chat UX、工具修复 |

详见 [CHANGELOG.md](CHANGELOG.md)。

---

## 安全

- **不要提交** API key、`.env` 或 `~/.nanobot/config.json`
- 曾粘贴到聊天/终端的密钥请轮换
- 本仓库刻意不包含 delivery 科学包与大模型权重

---

## 许可与归属

Agent 打包与桥接代码属于本项目。delivery 中的 AlphaFold3 权重 / RhoBind checkpoint 遵循上游许可，不得在未授权范围内再分发。

Nanobot 运行时：[HKUDS/nanobot](https://github.com/HKUDS/nanobot)。
