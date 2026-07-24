<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="480">

  <h1>nanobot-bio</h1>

  <p><b>RNA–RBP 结合预测 Agent</b></p>
  <p>
    编排栈基于 <a href="https://github.com/HKUDS/nanobot">Nanobot</a>；科学分数只来自 delivery。<br/>
    主路径：<em>检索供体 → 借头预测 → 整合</em><br/>
    产出：可供 Delivery 验收的 JSON verdict
  </p>

  <p>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot 源码"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/tests-120%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/stages-0%E2%86%921%E2%86%922%E2%86%923-green" alt="Stages">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p>
    <a href="#-克隆-https">克隆</a> ·
    <a href="#定位">定位</a> ·
    <a href="#能力">能力</a> ·
    <a href="#-快速开始">快速开始</a> ·
    <a href="#分层架构">架构</a> ·
    <a href="#配置与环境">配置</a> ·
    <a href="#命令与验收">命令</a> ·
    <a href="#测试与排错">测试</a> ·
    <a href="#文档索引">文档</a>
  </p>

  <p><a href="README.md">English</a> · <b>中文</b></p>
</div>

---

<div align="center">

### 四层分工一眼看清

| 层 | 落点 | 做什么 |
|:--:|:----:|:-------|
| **Controller** | 仓内 `nanobot/` | Stage 规划、两处 LLM checkpoint、出 JSON |
| **Toolkit** | `nanobot/agent/tools/rbp/` | sequence / structure / function / integrate |
| **Predictor** | `rhobind_agent_delivery` | 唯一可信的 `prob` / `p_hat` 来源 |
| **Evaluator** | `rbp_eval/` | 离线 LOO、消融、evolve-eval — 不进 chat |

</div>

> **协作约定：** 本仓只通过只读 JSON bridge 调 delivery，不改 registry、权重和 delivery 源码。验收以 `accept-golden` 为准，而不是 delivery 自带的 `run_example.sh`。

---

## 📦 克隆 (HTTPS)

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

科学包与本仓**平级**放置，不要塞进 git tree：

```text
bio_agent/
├── rbp-nanobot-bio/            ← 本仓库（编排 + slim Nanobot）
└── rhobind_agent_delivery/     ← registry · checkpoint · embedding / foldseek DB
```

从环境变量到验收门禁的完整说明见 [`INSTALL.md`](INSTALL.md)。国内若直连 GitHub 困难，可用镜像或代理后再 `git clone` 同一 HTTPS 地址。

---

## 定位

核心问题只有一句：**给定 RNA 序列与 RBP，是否结合？结合强度如何表述？**

产品入口是 `nanobot-bio agent` / `chat`。底层走 `Nanobot.from_config` → `run` / `run_streamed`。仓内 `nanobot/` 是裁掉 channels / WebUI 之后的 slim Controller，并挂载 RBP Toolkit SoT。LLM 只负责规划与解释；数值分数必须来自 delivery 工具。离线评测、自演进全部关在 `rbp_eval/`，避免和交互路径搅在一起。

最终对外交付物是 verdict JSON，字段固定为 `label`、`confidence`、`p_hat`、`explanation`、`supporting_rbps`。其中 `p_hat` 是 raw score，**不要**写成已校准的 P(bind)。

---

## 能力

### Stage 与路径

- Stage **0→1→2→3**，LLM checkpoint 两处：`commit_proxy_candidates`、`normalize_verdict`。
- **目录内**：`resolve_rbp` 命中 catalogue 后 own-head 预测一次即 **STOP**。
- **近同源**：`check_near_known`，identity ≥ 0.95 走 Fast Path。
- **未见靶标**：表征 → 并行检索 → `fuse_similarity_views` → `confidence_abstain` → 借 donor head 预测 → 整合。
- `turn_guards` + `stage_contract.py` 卡住顺序：fuse → commit → abstain → predict。
- Stage-3 checklist 失败 ≥2 项时，强制 `confidence=low`。

### 科学轴

- 序列：ESM-C embedding **与** MMseqs 双轴，不用 protein BLASTn。
- 结构：AFDB 优先；`use_af3_fallback` 默认开。探针失败只记 caveat，相似度不写成 `0`。
- 可选远同源：`RBP_PHMMER=1`。
- 工具策略：`RBP_RAW_TOOLS=whitelist` 默认策展集；调试可切 `all`。

### 离线演进

`evolve-eval` 在 nested-split 上比较 default vs retuned；`delta_auprc > 0` 或 HOLD 后才允许 `promote-evolved` 写入 `config/evolved.yaml`。过程 trace 落在 `artifacts/traces/`，便于复盘。

---

## ⚡ 快速开始

```bash
bash scripts/setup_all.sh                 # 完整科学栈
# bash scripts/setup_all.sh --skip-af3    # 跳过 AF3 加固
source .venv/bin/activate
nanobot-bio onboard && nanobot-bio doctor
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
# nanobot-bio chat
```

`doctor` 只做本地路径 / registry / skill / axes 一致性检查，不联网验 token。

---

## 分层架构

```text
                 用户 / Delivery 验收方
                           │
                           ▼
         nanobot-bio CLI → Nanobot.run / run_streamed
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
  nanobot/            app/backends/          rbp_eval/
  slim Controller      delivery bridge      离线 Evaluator
  + RBP Toolkit
       │                   │
       └─────────┬─────────┘
                 ▼
      rhobind_agent_delivery
      Predictor · DB · ready tools
```

| 层 | 代码位置 | 职责边界 |
|----|----------|----------|
| Controller | `nanobot/` | 工具规划、checkpoint、会话、出 verdict |
| Toolkit | `nanobot/agent/tools/rbp/` | 四视图 Tool 实现 |
| Bridge | `app/backends/delivery` | 子进程 + conda 隔离，只读调用 |
| Predictor | delivery `rhobind_predict` | 给出结合 `prob` |
| Evaluator | `rbp_eval/` | LOO / 消融 / evolve — 禁止混进 chat |

目录语义：`app/` 是产品壳；`nanobot/` 是 slim 框架与 Toolkit SoT；`artifacts/` 只装报告与 trace，可随时清空。

---

## 配置与环境

权威默认在 `config/defaults.yaml`。门禁通过后的候选落在 `config/evolved.yaml`。

| 变量 | 含义 |
|------|------|
| `BIO_ROOT` | 本仓与 delivery 的共同父目录 |
| `DELIVERY_ROOT` | `rhobind_agent_delivery` 根路径 |
| `NANOBOT_SRC` | 仓内 Nanobot，默认 `$NANOBOT_BIO_ROOT/nanobot` |
| `NANOBOT_BIO_ROOT` | 本仓根 |
| `NANOBOT_WORKSPACE` | 默认 `workspace/` |
| `NANOBOT_CONFIG` | `~/.nanobot/config.json` |
| `RBP_RAW_TOOLS` | `whitelist` · `all` · `none` |
| `NANOBOT_TOOL_ALLOW` | ToolLoader 白名单，默认 `rbp` |
| `RBP_PHMMER` | `1` 打开 phmmer 轴 |
| `HF_HOME` / `HF_ENDPOINT` | ESM 权重缓存 / 镜像 |
| `OMP_NUM_THREADS` | embedding 线程上限 |

Table 3 常用默认：`n_cand=5`，`tau_drop=0.30`，近同源 `0.95`，标签切分 `0.75 / 0.50 / 0.25`，供体聚合 `weighted`。

LLM 用 `nanobot-bio onboard` 写入本地配置。**API key 不得进仓库。**

---

## 命令与验收

| 命令 | 谁用 | 作用 |
|------|------|------|
| `doctor` | 所有人 | 路径 · registry · skill · axes / AF3 |
| `onboard` | 用户 | 配 provider / key |
| `agent` / `chat` | 用户 | 产品主路径 |
| `accept-golden` | Delivery | own-head 金标，PTBP1 × pos ≈ 0.966 |
| `accept-llm` | Delivery | LLM 触点证据包 |
| `gap-closure` | Delivery | Stage-0 / 顺序 fixture |
| `eval-plan` | 科研 | 消融与指标报告 |
| `evolve` / `evolve-eval` | 科研 | 离线自演进 |
| `promote-evolved` | 科研 | gate 后晋升配置 |
| `layout` / `gate` | CI | SoT 与工程门禁 |

报告默认写到 `artifacts/reports/`。协作方验收请走 **`accept-golden`**；delivery 仓内的 `run_example.sh` 只适合单工具排障，不算 app 验收。

Chat 内斜杠：`/help` · `/status` · `/tools` · `/new` · `/clear` · `/thinking` · `/onboard` · `/quit`

### 字段口径

| 字段 | 本产品含义 |
|------|------------|
| `p_hat` | predictor / `similarity_weighted_vote` 的 raw score |
| `confidence` | 规则 + Stage-3 checklist，不是校准概率 |
| `label` | `Strong` · `Likely` · `Unlikely` · `No` |

---

## 测试与排错

```bash
python -m pytest -q
# 基线：120 passed

pytest tests/test_proposal_compliance.py \
       tests/test_stage_contract.py \
       tests/test_section4_fidelity.py -q
```

先跑 `nanobot-bio doctor`，再对症处理：

| 现象 | 处理 |
|------|------|
| Config missing | `nanobot-bio onboard` |
| `DELIVERY_ROOT` 找不到 | 检查同级 delivery，或显式 export |
| `import nanobot` 指到旁路包 | 卸掉 `nanobot-ai`，`pip install -e .` |
| skill 不同步 | `python -m app.sync_overlay` |
| AF3 探针失败 | 记 caveat，回退 AFDB / 序列轴 |
| ESM OOM `rc=-9` | 提高 `protein_embed` 内存，设置 `HF_HOME` |

---

## 文档索引

| 文档 | 用途 |
|------|------|
| [INSTALL.md](INSTALL.md) | 安装、环境变量、验收流程 |
| [AGENTS.md](AGENTS.md) | Agent / CI 硬约束 |
| [RELEASE.md](RELEASE.md) | 发版步骤 |
| [CHANGELOG.md](CHANGELOG.md) | 变更记录 · 当前 **v0.5.1** |
| [VENDOR.md](VENDOR.md) | slim Nanobot 维护说明 |
| [README.md](README.md) | English |

本地 `docs/` 含提案与工程指南副本，**不推送 GitHub**，需要时在协作方之间单独分发。

---

<div align="center">

**致谢**

Controller 源自 [HKUDS/nanobot](https://github.com/HKUDS/nanobot)，本仓以 slim 形式放在 `nanobot/`。<br/>
Predictor 与 ready tools 来自 `rhobind_agent_delivery`，经只读 bridge 接入。<br/>
本仓库不修改 delivery 的源码、权重或 registry。

</div>
