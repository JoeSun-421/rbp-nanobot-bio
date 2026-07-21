# nanobot-bio

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.3.0-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

[English](README.md) | **中文**

面向 RNA–RBP 相互作用 *in silico* 评估的应用层。CLI `rbp-agent` 通过 [Nanobot](https://github.com/HKUDS/nanobot) 编排只读科学工具包（`rhobind_agent_delivery`）。结合分数仅来自预测工具；语言模型负责规划工具调用并生成有据解释。

## 功能

- **目录内（Stage 0）：** resolve → own-head `predict_interaction` → JSON verdict
- **迁移路径：** 多视角检索（序列 / 结构 / 功能）→ donor head → integrate
- **隔离科学后端：** conda 中的 RhoBind、ESM、Foldseek；可选 AF3；agent 侧 RNA 相似度
- **评测：** light LOO、evaluation-plan 消融、nested-split evolve-eval
- **安全默认：** 禁用 shell / 通用网络工具；OOM 时 `p_hat=null`，不臆造分数

## 架构

```text
rbp-agent (App)  →  Nanobot 运行时 ($NANOBOT_SRC)  →  delivery ($DELIVERY_ROOT，只读)
     │                      │
     ├─ config/             ├─ 自 nanobot/agent/tools/rbp/ 同步的工具
     ├─ rbp_eval/           └─ 自 nanobot/skills/rbp-agent/ 同步的 skill
     └─ artifacts/
```

| 层 | 职责 |
|----|------|
| App | CLI、桥接、配置、验收、SoT 同步 |
| Runtime | Agent 循环、工具注册、会话 |
| Science | 无状态预测器与数据库（本仓不修改） |

## 环境要求

- Python ≥ 3.10
- 同级 Nanobot 运行时与 `rhobind_agent_delivery`（通常位于同一 `BIO_ROOT`）
- 可选：GPU 与 delivery 提供的 conda 环境（RhoBind / ESM / AF3）

## 安装

```bash
cd nanobot-bio
bash scripts/setup_all.sh
source .venv/bin/activate
```

配置 LLM（OpenAI 兼容）：

```bash
rbp-agent onboard
```

## 快速开始

```bash
rbp-agent doctor
rbp-agent mvp
rbp-agent agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
rbp-agent chat
```

## 命令

| 命令 | 用途 |
|------|------|
| `doctor` | 路径、registry、skill 同步、模型能力矩阵 |
| `onboard` | LLM 厂商 / API key / 模型 |
| `mvp` / `own-head` | 验收路径 |
| `agent` / `chat` | 产品 Nanobot 运行 |
| `eval-plan` / `evolve` / `evolve-eval` | 离线评测与策略候选 |
| `layout` / `gate` / `compliance` | 工程检查 |

## 配置

默认值见 [`config/defaults.yaml`](config/defaults.yaml)（阈值、融合权重、`models:` 元数据）。仅当 `evolved: true` 且门禁通过时使用 `config/evolved.yaml`。

## 评测

- Light LOO 使用 delivery 的 transfer CSV，不在全量 FASTA 上重算 RhoBind。
- 晋升 evolved 配置需工程门禁 **且** nested-split 证据（`delta_auprc > 0`）；否则保留 candidate。

## 限制

- 部分 GPU 上 AF3 可能不可用；默认 AFDB → Foldseek。
- 默认 RNA 相似度为 mock；未配置真实 checkpoint 前 `rna_*` 融合权重为 0。
- 标签阈值校准需要外部 `{p_hat, y}`。

## 文档

| 文档 | 内容 |
|------|------|
| [docs/工程指南.zh.md](docs/工程指南.zh.md) | 契约、E2E、AF3、改动门禁（§9） |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |

## 引用

请同时引用 delivery 科学方法（RhoBind LOO / DESIGN）、Nanobot 运行时，以及本应用版本（如 v0.3.0）。

## 安全

勿提交 API key、`.env` 或 `~/.nanobot/config.json`；日志中出现过的密钥应轮换。

## 许可

应用打包与桥接代码属本项目。Delivery 权重与 checkpoint 遵循上游许可。运行时：[HKUDS/nanobot](https://github.com/HKUDS/nanobot)。
