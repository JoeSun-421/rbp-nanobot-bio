# nanobot-bio

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.4.0-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

[English](README.md) | **中文**

面向 RNA–RBP 相互作用 *in silico* 评估的应用层。CLI `nanobot-bio`（别名 `rbp-agent`）通过 [Nanobot](https://github.com/HKUDS/nanobot) 编排只读科学工具包（`rhobind_agent_delivery`）。结合分数**只**来自预测工具；LLM 负责规划工具调用并写出有据解释。

## 仓库布局

```text
nanobot-bio/
  app/           # CLI、delivery 桥、chat UX、overlay 同步
  plugin/        # 插件 SoT：skills/rbp-agent + agent/tools/rbp
  config/        # defaults.yaml / evolved.yaml
  rbp_eval/      # 离线 LOO / eval-plan / evolve-eval / accept-llm
  scripts/       # setup / CI
  tests/         # pytest
  docs/          # 本地工程说明（安装不依赖）
```

| 层 | 路径 | 职责 |
|----|------|------|
| App | `app/` | CLI、桥接、读配置、同步到运行时 |
| Plugin SoT | `plugin/nanobot/` | Skill + RBP 工具（同步到 `$NANOBOT_SRC`） |
| Eval | `rbp_eval/` | 离线验证 / 自演进（不在线改权重） |
| Science | `$DELIVERY_ROOT` | 只读 RhoBind / 检索库（本仓不改） |
| Runtime | `$NANOBOT_SRC` | Nanobot agent 循环 |

## 能力

- **目录内（Stage 0）：** `resolve_rbp` → own-head `predict_interaction` → JSON → STOP
- **近同源：** 序列一致度 ≥ 95% → 有 head 的 donor 预测一次 → STOP
- **未见：** 表征 → 并行检索 → fuse → **abstain** → 预测 donors → integrate → JSON
- **隔离：** 重型 torch / mmseqs 走 conda 子进程
- **诚实：** 不编造 `p_hat`；结构失败不当相似度 0；`confidence` 为规则/checklist（**不是**校准结合概率）

## 环境要求

- Python ≥ 3.10
- 同级 Nanobot 运行时（`$NANOBOT_SRC`）与 `rhobind_agent_delivery`（`$DELIVERY_ROOT`）
- 可选：GPU 与 delivery conda 环境

## 安装

```bash
cd nanobot-bio
bash scripts/setup_all.sh
source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
```

## 快速开始

```bash
nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
nanobot-bio chat
```

## 命令

| 命令 | 对象 | 用途 |
|------|------|------|
| `doctor` / `onboard` | 用户 | 路径、registry、skill、LLM |
| `agent` / `chat` | 用户 | 产品主路径 |
| `dev accept-golden` / `dev accept-llm` / `dev eval-plan` | 维护者 / Delivery | 验收与评测 |
| `dev loo-heavy` / `dev evolve-eval` | 维护者 | 离线科学闭环 |

## 配置

见 [`config/defaults.yaml`](config/defaults.yaml)。仅当 `evolved: true` 且门禁通过时使用 `config/evolved.yaml`。

## 对 Delivery / Proposal

- **禁止**在本 App 修改 `rhobind_agent_delivery/`
- 产品形态是 LLM Agent（`Nanobot.run`），不是固定 Python DAG
- `score_calibration` 为 Delivery **v2**（未进 registry）— 不得宣称已概率校准
- 冲突台账：`docs/冲突台账.zh.md`；现状：`docs/STATUS.md`

## 版本

见 `CHANGELOG.md`。
