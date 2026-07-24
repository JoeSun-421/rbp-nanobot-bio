<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="460">
  <h1>nanobot-bio</h1>
  <p><b>RNA–RBP 结合预测 Agent</b></p>
  <p>编排「检索供体 → 借头预测 → 整合」，产出可审计 JSON 判定。<br/>
  基于 <a href="https://github.com/HKUDS/nanobot">Nanobot</a> · 分数来自 <code>rhobind_agent_delivery</code>（只读桥）。</p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/stages-0%E2%86%921%E2%86%922%E2%86%923-green" alt="Stages">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
  <p><a href="README.md">English</a> · <b>中文</b></p>
</div>

---

## 🧭 导航

| | |
|---|---|
| [📦 克隆](#-克隆-https) | [⚡ 快速开始](#-快速开始) |
| [🏗️ 架构](#️-架构) | [📁 布局](#-仓库布局) |
| [🔀 控制流](#-控制流) | [⚙️ 配置](#️-配置) |
| [💻 命令](#-命令) | [🧪 测试](#-测试) |
| [🔧 排错](#-排错) | [📚 文档](#-文档) |

---

## 📦 克隆 (HTTPS)

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

delivery 包放在**同级目录**（不要放进本仓）：

```text
bio_agent/
├── rbp-nanobot-bio/          # 本仓库
└── rhobind_agent_delivery/   # 科学包（registry / 权重 / DB）
```

完整安装 / 环境 / 验收：**[`INSTALL.md`](INSTALL.md)**。

---

## ⚡ 快速开始

```bash
bash scripts/setup_all.sh          # 或: --skip-af3 / --skip-conda
source .venv/bin/activate
nanobot-bio onboard && nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
# nanobot-bio chat
```

---

## ✨ 能力一览

| 模块 | 要点 |
|------|------|
| **Stages** | `0→1→2→3`，两处 LLM checkpoint（`commit_proxy_candidates` / `normalize_verdict`） |
| **路径** | 目录内（own-head → STOP）· 近同源（identity ≥ 0.95）· 未见（检索 → fuse → abstain → predict → 整合） |
| **序列** | 双轴：ESM-C embedding + MMseqs |
| **结构** | AFDB 优先；AF3 fallback 默认开（探针失败 → caveat，不记 sim `0`） |
| **契约** | `turn_guards`：fuse → commit → abstain → predict |
| **Verdict** | JSON schema + Stage-3 checklist（≥2 失败 → `confidence=low`） |
| **工具包** | `nanobot/agent/tools/rbp/` · 四视图 · delivery JSON 桥 |
| **评测** | `rbp_eval/` 仅离线（LOO / 消融 / evolve-eval） |

---

## 🏗️ 架构

```text
用户 / Delivery 验收
        │
        ▼
nanobot-bio CLI  →  Nanobot.run / run_streamed
        │
        ├─ nanobot/                 Controller + Toolkit SoT
        ├─ app/backends/delivery    只读 JSON 桥
        └─ rbp_eval/                离线 Validation Evaluator
                │
                ▼
        rhobind_agent_delivery      Predictor + DBs + ready 工具
```

| 层 | 位置 | 职责 |
|----|------|------|
| Agent Controller | 仓内 `nanobot/` | 规划工具、触点、输出 JSON |
| Toolkit | `nanobot/agent/tools/rbp/` + 桥 | 序列 / 结构 / 功能 / 整合 |
| Predictor | delivery `rhobind_predict` | 结合 `prob` |
| 离线评测 | `rbp_eval/` | LOO、消融、evolve-eval |

---

## 📁 仓库布局

```text
nanobot-bio/
├── app/          # 产品壳：cli/{user,accept,eval,maint}、agent、桥
├── nanobot/      # 精简运行时 + skills/rbp-agent + agent/tools/rbp
├── config/       # defaults.yaml（Table 3）+ evolved.yaml
├── rbp_eval/     # 离线评测 / 演进
├── scripts/      # setup_all.sh、CI
├── tests/        # pytest
├── docs/         # 仅本地（不推 GitHub）
├── workspace/    # Nanobot 工作区
└── artifacts/    # reports / traces / cache（gitignore）
```

---

## 🔀 控制流

| 路径 | 步骤 |
|------|------|
| **目录内** | `resolve_rbp` → `in_panel` → `predict_interaction` ×1 → JSON → **STOP** |
| **近同源** | `check_near_known`（≥0.95）→ 有 head donor ×1 → JSON → **STOP** |
| **未见** | 表征 → 检索 → `fuse_similarity_views` → `confidence_abstain` → 借头预测 → 整合 → JSON |

默认（`config/defaults.yaml`）：`n_cand=5`，`tau_drop=0.30`，近同源 `0.95`，切分 `0.75/0.50/0.25`，聚合 `weighted`。

---

## ⚙️ 配置

Table 3：`config/defaults.yaml`。晋升候选：`config/evolved.yaml`。

| 变量 | 用途 |
|------|------|
| `BIO_ROOT` | 本仓与 delivery 的父目录 |
| `DELIVERY_ROOT` | `rhobind_agent_delivery` 根 |
| `NANOBOT_SRC` | 仓内运行时（`$NANOBOT_BIO_ROOT/nanobot`） |
| `NANOBOT_BIO_ROOT` | 本仓根 |
| `NANOBOT_WORKSPACE` | 默认 `workspace/` |
| `NANOBOT_CONFIG` | `~/.nanobot/config.json` |
| `RBP_RAW_TOOLS` | `whitelist` / `all` / `none` |
| `NANOBOT_TOOL_ALLOW` | ToolLoader 白名单（默认 `rbp`） |
| `RBP_PHMMER` | `1` = 启用 phmmer 轴 |
| `HF_HOME` / `HF_ENDPOINT` | ESM 缓存 / 镜像 |
| `OMP_NUM_THREADS` | embedding 线程上限 |

LLM：`nanobot-bio onboard` → `~/.nanobot/config.json`。**勿提交 API key。**

---

## 💻 命令

| 命令 | 用途 |
|------|------|
| `doctor` | 路径、registry、skill、axes / AF3 |
| `onboard` | LLM provider / API key |
| `agent` / `chat` | 产品主路径 |
| `accept-golden` | Own-head 金标（~0.966） |
| `accept-llm` | LLM 触点证据 |
| `gap-closure` | Stage-0 / 顺序 fixture |
| `eval-plan` | 消融 / 指标 |
| `evolve` / `evolve-eval` | 离线自演进 |
| `promote-evolved` | 门禁后 promote |
| `layout` / `gate` | SoT + 工程门 |

报告 → `artifacts/reports/`。验收权威：**`accept-golden`**。

<details>
<summary>Chat 斜杠命令</summary>

| 命令 | 用途 |
|------|------|
| `/help` `/status` `/tools` | 帮助 / 状态 / 工具列表 |
| `/new` `/clear` `/thinking` | 新会话 / 清屏 / 思考可见 |
| `/onboard` `/quit` | 重配 LLM / 退出 |

</details>

---

## 🎯 范围

| 本仓 | 非本仓 |
|------|--------|
| CLI、skill、策展工具、delivery **桥** | 改 delivery 源码 / 权重 / registry |
| 离线评测（`rbp_eval/`） | 在线写权重；编造 `p_hat` |
| JSON verdict + Stage 守卫 | 未注册的 Delivery v2 工具 |
| 有据 LLM 解释 | 无 ECE 时宣称校准 P(bind) |

| 字段 | 含义 |
|------|------|
| `p_hat` | 预测器 / vote 原始分（非校准 P） |
| `confidence` | 规则 + Stage-3 checklist |
| `label` | `Strong` / `Likely` / `Unlikely` / `No`（Table 3 切分） |

---

## 🧪 测试

```bash
python -m pytest -q
# 120 passed

pytest tests/test_proposal_compliance.py tests/test_stage_contract.py tests/test_section4_fidelity.py -q
```

---

## 🔧 排错

```bash
nanobot-bio doctor
```

| 现象 | 处理 |
|------|------|
| Config missing | `nanobot-bio onboard` |
| `DELIVERY_ROOT` 缺失 | 同级 `rhobind_agent_delivery` 或设环境变量 |
| `import nanobot` 指错 | 卸载 `nanobot-ai`；`pip install -e .` |
| skill 不同步 | `python -m app.sync_overlay` |
| AF3 探针失败 | caveat + AFDB/序列回退（可预期） |
| ESM OOM（`rc=-9`） | 提高 cgroup 内存；设置 `HF_HOME` |

---

## 📚 文档

| 文档 | 职责 |
|------|------|
| [INSTALL.md](INSTALL.md) | 安装 / 环境 / 验收 |
| [AGENTS.md](AGENTS.md) | Agent 与 CI 门禁 |
| [RELEASE.md](RELEASE.md) | 发版流程 |
| [CHANGELOG.md](CHANGELOG.md) | 变更历史 · **v0.5.1** |
| [VENDOR.md](VENDOR.md) | Slim vendor 笔记 |
| [README.md](README.md) | English |

---

## 🙏 致谢

Controller 源自 [Nanobot](https://github.com/HKUDS/nanobot)（精简于 `nanobot/`）。预测器与工具：`rhobind_agent_delivery`（只读桥）——本仓不修改 delivery 源码、权重或 registry。
