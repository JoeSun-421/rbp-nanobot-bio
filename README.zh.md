# nanobot-bio

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-v0.5.1-green.svg)](https://github.com/JoeSun-421/rbp-nanobot-bio/releases)

[English](README.md) | **中文**

应用包，回答：*RNA \(R\) 是否与 RBP \(X\) 相互作用？*  
编排运行在 [Nanobot](https://github.com/HKUDS/nanobot) 上。科学分数**仅**由 `rhobind_agent_delivery` 中的工具产生（本仓只读桥接）。

| 文档 | 路径 | 用途 |
|------|------|------|
| 本 README | 仓根 | 安装、运行、验收（Delivery / 用户） |
| 提案 EN/ZH | [`docs/proposal.md`](docs/proposal.md) · [`docs/proposal.zh.md`](docs/proposal.zh.md) | 任务、阶段、表 2–3 |
| Delivery 要求镜像 | [`docs/delivery要求.zh.md`](docs/delivery要求.zh.md) | BUILD_SPEC / HANDOFF / registry 对照 |
| 整改清单 | [`docs/整改清单.zh.md`](docs/整改清单.zh.md) · [`docs/remediation-checklist.md`](docs/remediation-checklist.md) | 要求 × 实现矩阵 |

> `docs/` 默认本地（gitignore，`docs/worklog/` 除外）。交付方需要时单独提供副本。工具清单权威：`$DELIVERY_ROOT/agent/tools/registry.json`。

---

## 1. 范围与边界

| 本仓范围 | 非本仓范围 |
|----------|------------|
| Agent CLI、skill、策展工具、delivery **桥** | 修改 `rhobind_agent_delivery/` 源码、权重、registry |
| 离线评测 / 演进（`rbp_eval/`） | 在线写权重；编造 `p_hat` / `prob` |
| JSON verdict + Stage 守卫 | registry 未收录的 Delivery **v2**（如 `score_calibration`） |
| LLM 规划 + 有据解释 | 在无校准工具与 ECE 证据时宣称校准 P(bind) |

**字段语义（验收措辞）：**

| 字段 | 本产品含义 |
|------|------------|
| `p_hat` | 来自预测器 / `similarity_weighted_vote` 的分数（raw）。不是 Delivery v2 校准概率。 |
| `confidence` | 规则 + Stage-3 checklist（及相关 flags）。不是校准 P(bind)。 |
| `label` | `{Strong, Likely, Unlikely, No}`，默认切分 0.75 / 0.50 / 0.25（Table 3）。 |

---

## 2. 架构（提案 §3 × Delivery 分层）

```text
用户 / Delivery 验收
        │
        ▼
nanobot-bio CLI  →  Nanobot.run / run_streamed
        │
        ├─ nanobot/ （skill + Tool）                   ← Toolkit SoT
        ├─ app/backends/delivery（JSON 桥）         ← 只读适配
        └─ rbp_eval/（离线 LOO / eval-plan / evolve）← Validation Evaluator
                │
                ▼
        rhobind_agent_delivery（Predictor + DB + ready 工具）
```

| 层 | 路径 / 环境 | 职责 |
|----|-------------|------|
| Agent Controller | Nanobot + `nanobot/skills/rbp-agent/SKILL.md` | 规划工具、两 LLM 触点、输出 JSON |
| Toolkit | `nanobot/agent/tools/rbp/` + delivery 脚本（经桥） | 序列 / 结构 / 功能 / 整合 |
| Predictor | delivery `rhobind_predict`（conda `rhobind`） | 结合 `prob` |
| 离线评测 | `rbp_eval/` | LOO、消融、evolve-eval（非 chat） |

---

## 3. 仓库布局

```text
nanobot-bio/
  app/                 # CLI、integrate、delivery bridge、core、dev（验收）
  nanobot/             # SoT（Proposal §6.2）：skills/rbp-agent + agent/tools/rbp
  config/defaults.yaml # Table-3、axes、fusion、models
  rbp_eval/            # 离线评测
  scripts/             # setup_all.sh、CI
  tests/               # pytest
  docs/                # 提案、delivery 镜像、清单（本地）
  workspace/           # 默认 Nanobot workspace（skill sync）
  artifacts/           # 运行时报告/trace/cache（gitignore）
```

运行时也可覆盖为 `~/.nanobot-bio/{workspace,artifacts}`。代码默认：仓根 `artifacts/`（`app.core.paths`）。
验收入口为顶层 CLI（`accept-golden` / `accept-llm` / `gap-closure`）；实现在 `app/dev/`。

---

## 4. 控制流（BUILD_SPEC × 提案阶段）

| 路径 | 步骤 |
|------|------|
| **目录内（Stage 0）** | `resolve_rbp` → `in_panel` → `predict_interaction` 一次 → JSON → **STOP** |
| **近同源** | `check_near_known`（一致度 ≥ 0.95）→ 有 head 的 donor 一次 → JSON → **STOP** |
| **未见** | 表征 → 并行检索（`hits_emb`+`hits_seq` 等）→ `fuse_similarity_views` → **`confidence_abstain`** → 对 donors `predict_interaction` → integrate → JSON |

默认（Table 3 / `config/defaults.yaml`）：`n_cand=5`，`tau_drop=0.30`，近同源 `0.95`，标签切分 `0.75/0.50/0.25`。

**Axes 说明：** 默认 `structure` / `rna_blastn` / `literature` 为 **true**；无 AFDB 时 **AF3 回退开启**（`use_af3` / `use_af3_fallback`）；探针失败记 caveat，≠ sim `0`。供体[...]

---

## 5. 环境要求

- Python ≥ 3.10  
- Nanobot：`$NANOBOT_SRC`  
- Delivery：`$DELIVERY_ROOT`  
- 可选 GPU 与 conda：`protein_embed`、`rna`、`rhobind`、`af3`  
- `agent` / `chat` / `accept-llm` 需要 LLM API（`nanobot-bio onboard`）

---

## 6. 安装

### 6.1 克隆仓库

#### 使用 HTTPS（推荐用于初次安装）
```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### 使用 SSH（需已配置 SSH 密钥）
```bash
git clone git@github.com:JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### 使用 GitHub CLI（需已安装 gh）
```bash
gh repo clone JoeSun-421/rbp-nanobot-bio
cd rbp-nanobot-bio
```

#### 指定特定分支（如 develop）
```bash
git clone --branch develop https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### 指定特定版本 tag（如 v0.5.1）
```bash
git clone --branch v0.5.1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### 浅克隆（仅克隆最新提交，加快速度）
```bash
git clone --depth 1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

#### 浅克隆指定分支
```bash
git clone --branch main --depth 1 https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio
```

### 6.2 安装依赖

```bash
bash scripts/setup_all.sh
# 或跳过 AF3 加固：
# bash scripts/setup_all.sh --skip-af3

source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
```

| 变量 | 用途 |
|------|------|
| `BIO_ROOT` | `nanobot-bio` 与 delivery 的父目录 |
| `DELIVERY_ROOT` | delivery 包根 |
| `NANOBOT_SRC` | 已安装 nanobot 或 clone |
| `NANOBOT_WORKSPACE` | 默认 `~/.nanobot-bio/workspace` |
| `AGENT_DB` / `RBP_REGISTRY` 等 | delivery / App env 注入 |

---

## 7. 命令

| 命令 | 对象 | 用途 |
|------|------|------|
| `nanobot-bio doctor` | 各方 | 路径、registry、skill、axes / AF3 状态 |
| `nanobot-bio onboard` | 用户 | LLM 配置 |
| `nanobot-bio agent` / `chat` | 用户 | 产品主路径 |
| `nanobot-bio accept-golden` | Delivery | Own-head 金标 |
| `nanobot-bio accept-llm` | Delivery | `nanobot_llm` + 触点证据 |
| `nanobot-bio gap-closure` | Delivery | Stage-0 / 顺序 fixture 证据包 |
| `nanobot-bio eval-plan` | Delivery / 科学 | 消融 / 指标协议 |
| `nanobot-bio layout` / `gate` | CI | SoT 布局 + 工程门禁 |

报告目录：仓内 `artifacts/reports/`（或环境覆盖到 `~/.nanobot-bio/artifacts/reports/`）。

```bash
nanobot-bio doctor
nanobot-bio accept-golden
nanobot-bio accept-llm
nanobot-bio gap-closure
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <seq>"
pytest tests/test_proposal_compliance.py -q
```

---

## 8. 配置

| 文件 | 内容 |
|------|------|
| [`config/defaults.yaml`](config/defaults.yaml) | `n_cand`、`tau_drop`、标签阈值、axes、fusion、abstain、llm、models |
| `config/evolved.yaml` | 仅在离线门禁通过并 promote 后使用 |

结构策略：AFDB（`structure_fetch`）优先于 AF3。结构失败不得记为相似度 `0`。

---

## 9. 符合性摘要

完整矩阵见 [`docs/整改清单.zh.md`](docs/整改清单.zh.md)。

| 项 | 相对提案 / Delivery |
|----|---------------------|
| P0 工具 + Stage 0 STOP | 已具备 |
| 双轴序列 + fuse + 预测前 abstain | skill/工具已具备 |
| Integrate E1–E4 | 已桥接 delivery |
| ready 工具注册（`all`） | 已具备 |
| 校准 P(bind) / `score_calibration` | **不宣称**；v2 OUT |
| 默认 axes 全开 | 以验收机 `defaults.yaml` 为准 |
| AF3 探针 | 视主机 `.af3_status` |
| 全 panel LOO / ECE | 有命令；有报告方可引用数值 |

---

## 10. 版本

见 [`CHANGELOG.md`](CHANGELOG.md)。当前 tag：**v0.4.0**。
