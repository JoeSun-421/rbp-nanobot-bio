# nanobot-bio

[English](README.md) | **中文**

面向 **RNA–RBP 相互作用**判定的 LLM 智能体。产品路径是真正的工具调用 agent（`Nanobot.run` + skills + delivery 桥接），不是固定流水线。

本仓库仅包含 **agent 产品包**。科学工具、checkpoint 与数据库在旁路 delivery 包（`rhobind_agent_delivery/`，运行时只读）中。

---

## 能做什么

输入蛋白（名称 / UniProt / 序列）及可选 RNA 上下文后，智能体会：

1. 判断该 RBP 是否在目录中（**Stage 0**）
2. 走 own-head 预测，或检索相似 donor 再 transfer
3. 输出结构化结论（`label`、`p_hat`、`confidence`、证据）——**禁止编造分数**

| 路径 | 适用 | 流程 |
|------|------|------|
| Stage 0 | 目录内 RBP | `resolve_rbp` → `predict_interaction` → JSON → **停止** |
| Transfer | 未见 / 强制 | 检索 → donor 预测 → integrate → JSON |

---

## 仓库结构

本仓库在 `nanobot/` 下只保留提案 **§6.2 覆盖层**（skills + `tools/rbp`）。该目录是**同步用的 SoT**，不是可 import 的 Python 包（无顶层 `__init__.py`）。完整 nanobot 框架作为**旁路运行时**（`pip install -e $BIO_ROOT/nanobot`）。`activate_env.sh` 会把覆盖层同步进该运行时。

```text
nanobot-bio/                   # 本 git 仓库
  nanobot/                     # 仅 §6.2 SoT — 不是完整框架
    skills/rbp-agent/SKILL.md
    agent/tools/rbp/*.py
  backends/delivery/           # 桥接 delivery 脚本（conda 环境）
  core/                        # onboard / chat UX / verdict schema
  rbp_eval/                    # traces 与自演化辅助
  cli.py                       # rbp-agent 入口
  integrate.py                 # RBPAgent → Nanobot.from_config().run
  scripts/activate_env.sh      # 环境激活 + 覆盖层同步
```

期望的旁路布局（不在本 git 仓库内）：

```text
bio_agent/
  nanobot/                     ← 运行时；import nanobot → 这里
  nanobot-bio/                 ← 本包
  rhobind_agent_delivery/      ← 科学包（设置 DELIVERY_ROOT）
```

布局验收：

```bash
python scripts/check_proposal_62_layout.py
```
---

## 环境要求

- Python ≥ 3.10（产品 venv）
- Delivery 科学 conda：`protein_embed`、`rna`、`rhobind`（AF3 可选）
- **理想科学环境：** CUDA GPU + ≥ 8–16 GiB 内存（HANDOFF `device=cuda`）。工具默认 `auto`，有卡则用 CUDA
- LLM：`rbp-agent onboard` 选择厂商与模型（写入 `~/.nanobot/config.json`，供 `Nanobot.from_config`）
- ESM 需本地 Hugging Face 权重 / 镜像。`activate_env.sh` 会设置 `HF_HOME` 与 `HF_ENDPOINT`

---

## 快速开始

```bash
export BIO_ROOT=/path/to/bio_agent          # nanobot-bio 与 delivery 的父目录
export DELIVERY_ROOT=$BIO_ROOT/rhobind_agent_delivery

source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh
# 安装旁路 nanobot + 本包，并同步 §6.2 tools/skill

rbp-agent onboard              # 选择厂商 + 模型 + API key
rbp-agent onboard --list-models
rbp-agent doctor               # 健康检查
rbp-agent chat                 # Nanobot.run 交互式对话
# 科学工具默认 --device auto（有 GPU 用 cuda）：
rbp-agent agent --example pos --strict
```
科学环境一次性创建（在 delivery 内）：

```bash
bash $DELIVERY_ROOT/agent/setup_envs.sh
# 或按需：protein_embed / rna / rhobind / af3
```

---

## CLI

| 命令 | 用途 |
|------|------|
| `rbp-agent onboard` | 选择 LLM 厂商 + 模型 + API key |
| `rbp-agent doctor` | 检查 delivery + conda |
| `rbp-agent chat` | 交互式 agent |
| `rbp-agent agent` | 单次运行（`--example` / `--message` / `--force-transfer`） |
| `rbp-agent own-head` | Own-head 烟测（无 LLM） |
| `rbp-agent predict` | 直接调用 predict API |

```bash
# Own-head 黄金样例（无 LLM）— 期望 p_hat ≈ 0.966
rbp-agent own-head

# 同一案例走 agent
rbp-agent agent --example pos --strict

# 强制 transfer
rbp-agent agent --message "..." --force-transfer
```

---

## 行为约束

- 产品路径只有 **`Nanobot.run`**（无固定 `core/pipeline`）
- **禁止伪造 `p_hat`**。predict OOM / 超时：`p_hat=null`，不重试
- Stage 0 在 own-head 成功后必须停止
- `rhobind_agent_delivery/` 下科学代码 **只读**——仅通过 bridge 调用
- 禁止提交 API key 或含密钥的 `.env`

---

## 验收

科学 golden 以 delivery 包为准（own-head ≈ **0.966**，AUPRC 0.9311）。本地有 delivery 时：

```bash
# Delivery 原厂烟测（不经 nanobot）
bash $DELIVERY_ROOT/agent/examples/run_example.sh cpu
```

逐步期望输出见 delivery 的 `agent/examples/README.md`。

---

## 配置

| 变量 | 作用 |
|------|------|
| `BIO_ROOT` | 含 agent + delivery + 旁路 nanobot 的工作区根目录 |
| `DELIVERY_ROOT` | `rhobind_agent_delivery` 路径 |
| `NANOBOT_SRC` | 旁路 nanobot 运行时（默认 `$BIO_ROOT/nanobot`） |
| `NANOBOT_WORKSPACE` | Agent 工作区（默认 `nanobot-bio/workspace`） |
| `NANOBOT_CONFIG` | LLM 配置（默认 `~/.nanobot/config.json`） |
| `RHOBIND_DEVICE` | `auto`（默认）/ `cuda` / `cpu` — 科学工具设备 |
| `HF_HOME` / `HF_ENDPOINT` | 本地 HF 缓存与镜像（由 `activate_env.sh` 设置） |

### LLM 厂商

`rbp-agent onboard` 写入 nanobot 配置（`agents.defaults.provider/model` + `providers.*`）。预置厂商包括 OpenAI、Anthropic、DeepSeek、Gemini、通义 Qwen、智谱、Moonshot、Mistral、MiniMax、OpenRouter、Groq、SiliconFlow，以及任意 OpenAI 兼容自定义 endpoint。可用 `rbp-agent onboard --list-models` 查看模型列表。

可将 [`.env.example`](.env.example) 复制为 `.env` 做本地覆盖（已 gitignore）。

---

## 许可说明

Agent 包装与 bridge 代码属本项目。Delivery 包内的 AlphaFold3 权重 / RhoBind checkpoint 受上游许可约束，不得在未授权范围外分发。
