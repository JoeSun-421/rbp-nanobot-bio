<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="460">
  <h1>nanobot-bio</h1>
  <p>基于 Nanobot 的 RNA–RBP 结合预测 Agent。<br/>
  编排「检索供体 → 借头预测 → 整合」，产出可审计的 JSON 判定。</p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/stages-0%E2%86%921%E2%86%922%E2%86%923-green" alt="Stages">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
  <p><a href="README.md">English</a> · <b>中文</b></p>
</div>

## 🧭 导航

- [克隆](#-克隆-https)
- [概述](#概述)
- [特性](#特性)
- [快速开始](#-快速开始)
- [架构](#架构)
- [仓库布局](#仓库布局)
- [控制流](#控制流)
- [配置](#配置)
- [命令](#命令)
- [范围与边界](#范围与边界)
- [测试](#测试)
- [排错](#排错)
- [文档](#文档)

---

## 📦 克隆 (HTTPS)

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

delivery 包与本仓放在**同级**：

```text
bio_agent/
├── rbp-nanobot-bio/           ← 本仓库
└── rhobind_agent_delivery/    ← 科学包：registry、权重、DB
```

安装、环境变量、数据与验收见 [`INSTALL.md`](INSTALL.md)。

---

## 概述

`nanobot-bio` 回答一个问题：*RNA R 是否与 RBP X 相互作用？*

- 编排使用仓内 **精简 Nanobot** `nanobot/`，Proposal §6.2：Agent Controller + RBP 工具包，不含 Telegram / WebUI / channels。
- 科学分数**仅**来自 `rhobind_agent_delivery` 中的工具。本仓经只读 JSON 桥调用，不修改 delivery 源码、权重、registry。
- 离线评测与自演进在 `rbp_eval/`，与 chat 路径隔离。
- Agent 产出 JSON verdict，字段含 `label`、`confidence`、`p_hat`、`explanation`、`supporting_rbps`，供 Delivery 验收。

---

## 特性

### Agent 主循环

- **Stage 0→1→2→3** 四阶段语义，两处 LLM checkpoint：`commit_proxy_candidates` 与 `normalize_verdict`。
- **三条预测路径**：目录内 own-head 一次即停；近同源 identity ≥ 0.95 Fast Path；未见则检索 → fuse → abstain → 借头预测 → 整合。
- **双轴序列检索**：ESM-C embedding + MMseqs，不用 protein BLASTn。
- **结构轴**：AFDB 优先，AF3 fallback 默认开启；探针失败记 caveat，不写相似度 `0`。
- **Stage contract** 由 `turn_guards` 强制：fuse → commit → abstain → predict，顺序由 `stage_contract.py` 数据驱动。
- **JSON verdict schema** + Stage-3 checklist：≥2 项失败则强制 `confidence=low`。

### 工具包 — 单一来源

- 工具为 `nanobot.agent.tools.base.Tool` 子类，位于 `nanobot/agent/tools/rbp/`。
- 四视图：sequence、structure、function、integrate。
- delivery 脚本经 `app/backends/delivery` JSON 桥调用，子进程隔离、conda env 分离。
- `RBP_RAW_TOOLS=whitelist` 为默认策展集；`all` 开放全部 37 工具供调试；`none` 关闭 raw 工具。
- 可选 phmmer 远同源轴：设置 `RBP_PHMMER=1`。

### 离线评测与演进

- `rbp_eval/`：LOO、消融、evolve-eval，不进入 chat 路径。
- 自演进**仅离线**：`evolve-eval` 产出候选；`delta_auprc > 0` 或 HOLD 后门禁通过，再 promote 到 `config/evolved.yaml`。
- `RBPTraceHook` 写入 `artifacts/traces/*.jsonl`，供回放与归因。

---

## ⚡ 快速开始

```bash
bash scripts/setup_all.sh
# 轻量：bash scripts/setup_all.sh --skip-af3
source .venv/bin/activate
nanobot-bio onboard && nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
# nanobot-bio chat
```

---

## 架构

```text
用户 / Delivery 验收
        │
        ▼
nanobot-bio CLI  →  Nanobot.run / run_streamed
        │
        ├─ nanobot/                 ← Controller + Toolkit SoT
        ├─ app/backends/delivery    ← 只读 JSON 桥
        └─ rbp_eval/                ← 离线 Validation Evaluator
                │
                ▼
        rhobind_agent_delivery      ← Predictor + DBs + ready 工具
```

| 层 | 路径 | 职责 |
|----|------|------|
| Agent Controller | 仓内 `nanobot/`，`Nanobot.from_config` → `run` | 规划工具、两 LLM 触点、输出 JSON |
| Toolkit | `nanobot/agent/tools/rbp/` + 经桥的 delivery 脚本 | 序列 / 结构 / 功能 / 整合 |
| Predictor | delivery `rhobind_predict`，conda env `rhobind` | 结合 `prob` |
| 离线评测 | `rbp_eval/` | LOO、消融、evolve-eval — 非 chat |

---

## 仓库布局

```text
nanobot-bio/
├── app/                 # 产品壳：cli/{user,accept,eval,maint}、agent、delivery 桥
├── nanobot/             # 精简 vendor 框架 + skills/rbp-agent + agent/tools/rbp
├── config/              # defaults.yaml Table 3 + evolved.yaml
├── rbp_eval/            # 离线评测 / 演进
├── scripts/             # setup_all.sh、CI helpers
├── tests/               # pytest：contract / compliance
├── docs/                # 提案与清单 — 仅本地，不推 GitHub
├── workspace/           # 默认 Nanobot workspace，skill sync 目标
└── artifacts/           # 运行时报告 / traces / cache — gitignore
```

---

## 控制流

| 路径 | 步骤 |
|------|------|
| **目录内 — Stage 0** | `resolve_rbp` → `in_panel` → `predict_interaction` 一次 → JSON → **STOP** |
| **近同源** | `check_near_known`，identity ≥ 0.95 → 有 head 的 donor 一次 → JSON → **STOP** |
| **未见** | 表征 → 并行检索 `hits_emb`+`hits_seq` → `fuse_similarity_views` → `confidence_abstain` → 对 donors `predict_interaction` → 整合 → JSON |

默认来自 Table 3 / `config/defaults.yaml`：`n_cand=5`，`tau_drop=0.30`，近同源 `0.95`，标签切分 `0.75 / 0.50 / 0.25`，供体聚合 `weighted`，对应提案 §4 Σ s·p·c。

---

## 配置

默认在 `config/defaults.yaml`：Table 3 的 `n_cand`、`tau_drop`、标签阈值、axes、fusion、abstain、llm、models。`config/evolved.yaml` 仅在离线门禁通过并 promote 后使用。

| 变量 | 用途 |
|------|------|
| `BIO_ROOT` | `nanobot-bio` 与 delivery 的父目录 |
| `DELIVERY_ROOT` | delivery 包根 `rhobind_agent_delivery` |
| `NANOBOT_SRC` | 仓内精简运行时，默认 `$NANOBOT_BIO_ROOT/nanobot` |
| `NANOBOT_BIO_ROOT` | 本仓根 |
| `NANOBOT_WORKSPACE` | 默认 `nanobot-bio/workspace` |
| `NANOBOT_CONFIG` | LLM 配置 `~/.nanobot/config.json` |
| `RBP_RAW_TOOLS` | `whitelist` / `all` / `none` |
| `NANOBOT_TOOL_ALLOW` | ToolLoader 白名单，默认 `rbp` |
| `RBP_PHMMER` | 设为 `1` 启用可选 phmmer 轴 |
| `HF_HOME` / `HF_ENDPOINT` | ESM 权重缓存 / 镜像 |
| `OMP_NUM_THREADS` | embedding 工具线程上限 |
| `AGENT_DB` / `RBP_REGISTRY` | delivery setup / App env 注入 |

LLM：`nanobot-bio onboard` 写入 `~/.nanobot/config.json`。**不要提交真实 API key。**

---

## 命令

| 命令 | 对象 | 用途 |
|------|------|------|
| `nanobot-bio doctor` | 各方 | 路径、registry、skill sync、axes / AF3 状态 |
| `nanobot-bio onboard` | 用户 | LLM provider / API key |
| `nanobot-bio agent` / `chat` | 用户 | 产品主路径，`Nanobot.run` / streamed |
| `nanobot-bio accept-golden` | Delivery | Own-head 金标，delivery pos RNA × PTBP1 ≈ 0.966 |
| `nanobot-bio accept-llm` | Delivery | `nanobot_llm` 模式 + 触点证据 |
| `nanobot-bio gap-closure` | Delivery | Stage-0 / 顺序 fixture 证据包 |
| `nanobot-bio eval-plan` | Delivery / 科学 | 消融 / 指标协议 |
| `nanobot-bio evolve` / `evolve-eval` | 科学 | 离线 LOO batch + nested-split evolve |
| `nanobot-bio promote-evolved` | 科学 | 门禁通过后 promote 候选配置 |
| `nanobot-bio layout` / `gate` | CI | SoT 布局 + 工程门禁 |

报告目录：仓内 `artifacts/reports/`；若环境覆盖则为 `~/.nanobot-bio/artifacts/reports/`。

**验收权威路径：** `nanobot-bio accept-golden` 面向协作者，包装并扩展 delivery 原生 smoke。`rhobind_agent_delivery/agent/examples/run_example.sh` 是 delivery 内部回归、无 app 层，仅调试单工具时使用。

### Chat 斜杠命令

| 命令 | 用途 |
|------|------|
| `/help` | 查看帮助 |
| `/status` | 当前模型、工具、会话 |
| `/tools` | 列出已注册工具 |
| `/new` | 开启新会话 |
| `/clear` | 清屏 |
| `/thinking` | 切换思考可见性 |
| `/onboard` | 重新配置 LLM |
| `/quit` | 退出 |

---

## 范围与边界

| 本仓范围 | 非本仓范围 |
|----------|------------|
| Agent CLI、skill、策展工具、delivery **桥** | 修改 `rhobind_agent_delivery/` 源码、权重、registry |
| 离线评测 / 演进 `rbp_eval/` | 在线写权重；编造 `p_hat` / `prob` |
| JSON verdict + Stage 守卫 | registry 未收录的 Delivery v2：校准、motif、saliency、HDOCK |
| LLM 规划 + 有据解释 | 无校准工具与 ECE 证据时宣称校准 P(bind) |

| 字段 | 本产品含义 |
|------|-----------|
| `p_hat` | 预测器 / `similarity_weighted_vote` 原始分，不是 Delivery v2 校准概率。 |
| `confidence` | 规则 + Stage-3 checklist 及相关 flags，不是校准 P(bind)。 |
| `label` | `Strong` / `Likely` / `Unlikely` / `No`，Table 3 对 `p_hat` 切分，默认 0.75 / 0.50 / 0.25。 |

---

## 测试

```bash
python -m pytest -q
```

当前基线：`120 passed`。

合规门禁：

```bash
pytest tests/test_proposal_compliance.py -q
pytest tests/test_stage_contract.py -q
pytest tests/test_section4_fidelity.py -q
```

---

## 排错

```bash
nanobot-bio doctor
```

| 现象 | 处理 |
|------|------|
| Config missing | `nanobot-bio onboard` |
| `DELIVERY_ROOT` 缺失 | 检查同级 `rhobind_agent_delivery` 或设置环境变量 |
| `NANOBOT_SRC` 缺失 | 期望仓内 `nanobot-bio/nanobot/` |
| skill 不同步 | `python -m app.sync_overlay` 或 `nanobot-bio doctor` |
| `import nanobot` 指向兄弟仓 / site-packages | 卸载 `nanobot-ai`，`pip install -e .`，`NANOBOT_BIO_ROOT` 置于 `PYTHONPATH` 最前 |
| AF3 探针失败 | 见 `.af3_status`；回退 AFDB / 序列轴并记 caveat |
| ESM killed / OOM `rc=-9` | 提高 `protein_embed` 的 cgroup 内存；`HF_HOME` 指向本地权重 |
| LLM API key 缺失 | `nanobot-bio onboard` |

---

## 文档

| 文档 | 职责 |
|------|------|
| [INSTALL.md](INSTALL.md) | 安装 / 环境 / 验收 |
| [AGENTS.md](AGENTS.md) | Agent 与 CI 门禁 |
| [RELEASE.md](RELEASE.md) | 发版流程 |
| [CHANGELOG.md](CHANGELOG.md) | 变更历史 — 当前 tag **v0.5.1** |
| [VENDOR.md](VENDOR.md) | Slim vendor 维护笔记 |
| [README.md](README.md) | English |

---

## 致谢

精简 Agent Controller 源自 [Nanobot](https://github.com/HKUDS/nanobot)，vendored 于 `nanobot/`，已去掉 channels / WebUI。科学预测器与 ready 工具来自 `rhobind_agent_delivery`，经只读桥接入。本仓不修改 delivery 源码、权重或 registry。
