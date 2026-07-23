# 项目提案全文中文译本（对照清单已核）

**原标题：** An Agentic Framework for Predicting RNA–RBP Interactions on Unseen Proteins  
**副标题：** Project Proposal · Internal Working Document · July 9, 2026  

> **核对说明（2026-07-23）：** 已与用户粘贴的英文全文逐段对照。粘贴稿中单独出现的数字 **1–8** 是 PDF **页码**，不是未翻译的「第 2–8 章」。提案正文止于 **§11 Open Risks** 与 *End of proposal*；**没有**第 12 章及以后。  
> **英文原文：** [`proposal.md`](proposal.md)  
> **性质：** 全文翻译，不增删义。标识符 / API 名保留英文。

## 全文对照清单（英文 → 本文）

| 英文原文 | 本文位置 | 状态 |
|----------|----------|------|
| Abstract | [摘要](#摘要) | 已译 |
| 1 Background and Motivation | [1 背景与动机](#1-背景与动机-1-background-and-motivation) | 已译 |
| 2 Task Definition | [2 任务定义](#2-任务定义-2-task-definition) | 已译 |
| 3 System Architecture | [3 系统架构](#3-系统架构-3-system-architecture) | 已译 |
| 3.1 High-Level Overview + Figure 1 | [3.1](#31-高层概览-31-high-level-overview) | 已译 |
| 3.2 Why an Agent (not a Fixed Pipeline) | [3.2](#32-为什么用智能体而不是固定流水线-32-why-an-agent-not-a-fixed-pipeline) | 已译 |
| 4 Detailed Workflow | [4 详细工作流](#4-详细工作流-4-detailed-workflow) | 已译 |
| Stage 0 / 1 / 2 / 3 | 见 §4 各小节 | 已译 |
| Table 1 | 表 1 | 已译 |
| 5 Tool Interface Specification + Table 2 | [5](#5-工具接口规范-5-tool-interface-specification) | 已译 |
| 6 Implementation on nanobot | [6](#6-在-nanobot-上的实现-6-implementation-on-nanobot) | 已译 |
| 6.1 / 6.2 / 6.3 | 见 §6 | 已译 |
| 7 Self-Evolving Mechanism | [7](#7-自演进机制-7-self-evolving-mechanism) | 已译 |
| 8 Default Design Decisions + Table 3 | [8](#8-默认设计决策-8-default-design-decisions) | 已译 |
| 9 Evaluation Plan | [9](#9-评估计划-9-evaluation-plan) | 已译 |
| 10 Milestones | [10](#10-里程碑-10-milestones) | 已译 |
| 11 Open Risks | [11](#11-开放风险-11-open-risks) | 已译 |
| End of proposal | 文末 | 已译 |

---

## 摘要

（英文：Abstract）

我们提出一个由 LLM 驱动的智能体，将一个预训练的 RNA–RBP 相互作用分类器，从已知 RNA 结合蛋白（RBP）的封闭集合扩展到任意、此前未见的 RBP。该智能体使用一套经过策展的生物信息学工具包（序列搜索、结构比对、功能注释）从训练目录中检索一小套相似的代理（proxy）RBP，在这些代理上运行分类器，并通过将代理概率与每个代理的相似度证据相融合，给出可解释的相互作用判定（verdict）。该框架实现在轻量智能体运行时 nanobot 之上，并设计为可自演进：工具包组成与融合权重对照 held-out 验证集周期性重调。

---

## 1 背景与动机（1 Background and Motivation）

团队已在固定的 \(N_{\mathrm{known}}\) 个 RNA 结合蛋白目录上训练了多类相互作用分类器 \(f_\theta(\mathrm{RNA},\mathrm{RBP})\to[0,1]\)。当被查询的 RBP 落在训练目录内时分类器准确，但其支持集无法朴素扩展：新 RBP 往往缺少训练数据，且对每个新靶点重训不切实际。

一个自然的变通是从训练目录中最接近的类似物借用强度：若查询 RBP 与一个或多个已知 RBP 高度相似，则分类器在这些类似物上的输出对查询是有信息的。以原则性、可解释且可扩展的方式实现这一想法，需要的不只是固定流水线——相似度本身是多面的（序列、结构、功能），且合适的聚合依赖于靶点。因此我们将系统框定为编排工具包并产出有依据判定的 LLM 智能体。

---

## 2 任务定义（2 Task Definition）

**输入（Input）。**

- RNA 序列 \(r\in\Sigma^*_{\mathrm{RNA}}\)。  
- 目标 RBP \(p^\star\)，由其 UniProt ID 与氨基酸序列标识（以及在可用时的三维结构）。

**输出（Output）。** 结构化判定

\[
V = \{\mathrm{label},\ \hat{p},\ \mathrm{confidence},\ \mathrm{explanation},\ \mathrm{supporting\ RBPs}\},
\]

其中 \(\mathrm{label}\) 属于 \(\{\mathrm{Strong},\mathrm{Likely},\mathrm{Unlikely},\mathrm{No}\}\)，\(\hat{p}\) 为校准后的相互作用概率。

**范围假设（Scope assumption）。** 我们假设团队维护已知 RBP 的目录

\[
\mathcal{K}=\{(p_i,\mathrm{seq}_i,\mathrm{struct}_i,\mathrm{annot}_i)\}_{i=1}^{N_{\mathrm{known}}},
\]

包含序列、结构（必要时经 AF3 缓存）与功能注释。

---

## 3 系统架构（3 System Architecture）

### 3.1 高层概览（3.1 High-Level Overview）

系统组织为三层（图 1）：

1. **智能体控制器 / Agent Controller（LLM）：** 解析查询、规划工具调用、融合异构证据，并撰写最终解释。  
2. **工具包层 / Toolkit Layer：** 通过 JSON-schema 函数调用暴露给 LLM 的生物信息学工具注册表。工具无状态，并分为三个视图——序列、结构与功能。  
3. **预测器层 / Predictor Layer：** 团队的预训练相互作用分类器（同样暴露为工具），以及记录 traces 以供离线自演进的 memory/log 组件。

```text
用户查询
(RNA 序列, 目标 RBP)
        │
        ▼
智能体控制器（经 nanobot 的 LLM）
路由 · 工具调度 · 证据融合 · 解释
        │
   ┌────┼────┐
   ▼    ▼    ▼
序列          结构              功能
ESM/MMseqs    AFDB/Foldseek(+AF3)  UniProt/文献
   │          │                 │
   └────┬─────┴─────────────────┘
        ▼
     工具包层
        │
        ▼
     预测器
     fθ(RNA,RBP)
     预测器层
        │
        ▼
记忆与 Trace 日志  ···(离线)···▶  验证评估器
供自演进使用                      工具权重 / 增补
```

**图 1：** 系统架构。实线箭头：每次查询的调用流。虚线箭头：离线 trace 记录与自演进反馈。  
（英文 Figure 1: System architecture. Solid arrows: per-query call flow. Dashed arrows: offline trace logging and self-evolution feedback.）

### 3.2 为什么用智能体（而不是固定流水线）（3.2 Why an Agent (not a Fixed Pipeline)）

工作流中有两部分需要 LLM 的灵活性，并在原始草图中被如此标注：

1. **异构证据融合（Heterogeneous evidence fusion）。** 功能注释是自由文本；将它们与数值型序列/结构分数结合，需要自然语言推理（例如「两者都含 RRM 结构域且作用于 pre-mRNA 剪接」），而不是手工调好的加权和。  
2. **可解释判定（Interpretable verdict）。** 下游用户需要知道为何给出预测。LLM 基于其所消费的工具输出给出忠实解释，这是固定流水线无法交付的。

---

## 4 详细工作流（4 Detailed Workflow）

智能体每次查询的行为分为四个阶段。

### Stage 0 — 查询解析与快速路径（Query Parsing and Fast Path）

智能体提取 \(\{r,p^\star\}\) 并检查 \(p^\star\in\mathcal{K}\)。

- **严格匹配（Strict match）**（UniProt ID 相等）⇒ **快速路径（Fast Path）：** 调用预测器一次并返回。  
- **近匹配（Near-match）**（与某个 \(p_i\in\mathcal{K}\) 的序列一致度 \(\ge 95\%\)）⇒ 使用所匹配代理的快速路径，并在解释中标注。  
- **否则** ⇒ 进入 Stage 1。

### Stage 1 — 多视图候选检索（Multi-View Candidate Retrieval）

智能体沿三个独立视图**并行**检索相似 RBP。

| 视图（View） | 工具（Tools） | 输出（Output） |
|--------------|---------------|----------------|
| 序列（Sequence） | BLASTn、ESM embeddings | Top-K 目录 RBP 及相似度分数；ESM 给出对远端同源更稳健的语义距离。 |
| 结构（Structure） | AF3（仅当 \(p^\star\) 本地无结构时）、USalign | Top-K 目录 RBP 及 TM-scores。 |
| 功能（Function） | UniProt、PDB、literature search | 自由文本注释（GO 术语、结构域、功能描述）。 |

**表 1（Table 1）：** Stage 1 检索视图。智能体在可能时并发发出这些调用；当 AF3 不可用或超时，结构视图回退到仅序列。

**LLM 融合（第一个 LLM 检查点）（LLM fusion, first LLM checkpoint）。** 智能体随后请 LLM 将三个候选列表与文本注释合并为至多 \(N_{\mathrm{cand}}=5\) 个代理候选的排序列表，每个标注为：

```json
{
  "rbp_id": "P12345",
  "similarity_score": 0.78,
  "similarity_breakdown": {
    "seq": 0.82,
    "struct": 0.61,
    "func": 0.85
  },
  "rationale": "与靶点共享 RRM 结构域；两者均注释为剪接因子；ESM 余弦相似度 0.81。"
}
```

（其中 `similarity_score` \(\in[0,1]\)，由 LLM 标定 / LLM-calibrated。）

指示 LLM 丢弃融合相似度低于可配置下限（\(\tau_{\mathrm{drop}}=0.30\)）的任何候选，因此 \(N_{\mathrm{cand}}\) 是上界，不是固定配额。

### Stage 2 — 在代理上调用预测器（Predictor Calls on Proxies）

对每个存活候选 \(p_i\)，智能体发出 \(\hat{p}_i=f_\theta(r,p_i)\)。调用相互独立且可批处理。预测器工具返回：

```json
{
  "rbp_id": "P12345",
  "prob": 0.84,
  "confidence": 0.91,
  "feature_attribution": {}
}
```

（`feature_attribution` 可选，用于解释。）

### Stage 3 — 聚合与解释（Aggregation and Explanation）

**数值聚合（Numeric aggregation）。** 以相似度加权平均作为确定性基线：

\[
\hat{p}=\frac{\sum_{i=1}^{N_{\mathrm{cand}}} s_i\cdot \hat{p}_i\cdot c_i}{\sum_{i=1}^{N_{\mathrm{cand}}} s_i\cdot c_i},
\]

其中 \(s_i\) 为 LLM 融合相似度，\(c_i\) 为预测器自报置信度。

**标签阈值（Label thresholds）。**

\[
\mathrm{label}=
\begin{cases}
\mathrm{Strong} & \hat{p}\ge 0.75 \\
\mathrm{Likely} & 0.50\le\hat{p}<0.75 \\
\mathrm{Unlikely} & 0.25\le\hat{p}<0.50 \\
\mathrm{No} & \hat{p}<0.25
\end{cases}
\]

阈值在验证集上重标定（§7）。

**LLM 解释（第二个 LLM 检查点）（LLM explanation, second LLM checkpoint）。** LLM 接收（\(p^\star\) 注释，\(\{(p_i,s_i,\hat{p}_i,c_i,\mathrm{rationale}_i)\}\)），并发出单个 JSON 对象，包含判定、支持 RBP，以及简洁（3–5 句）人类可读解释。注意事项（例如「一个高相似代理意见不一致」）被显式 surfacing。

---

## 5 工具接口规范（5 Tool Interface Specification）

所有工具遵循 nanobot 的 Tool 契约：名称、描述、JSON-schema 参数规范，以及异步 `execute` 方法。失败必须返回 `{status: "error", reason: ...}` 而不是抛出，以便智能体优雅回退。

| 优先级（Pri.） | 工具（Tool） | 目的（Purpose） |
|----------------|--------------|-----------------|
| P0 | `predict_interaction(rna, rbp_id)` | 核心分类器；返回 raw prob / attributions。 |
| P0 | `get_known_rbp_list()` / `resolve_rbp` | 目录 \(\mathcal{K}\) + in-panel 解析。 |
| P0 | `seq_similarity(target, candidates?)` | ESM-C + MMseqs 双轴（`hits_emb` / `hits_seq`）。 |
| P1 | `struct_similarity` / `structure_fetch` | AFDB 上 Foldseek（优先）；可选 USalign refine。 |
| P1 | `get_func_annotation` / `domain_architecture` | UniProt + PDB / 结构域文本注释。 |
| P1 | `fuse_similarity_views` / `confidence_abstain` | 多视图融合 + OOD abstain（transfer 上预测前）。 |
| P1 | `transfer_prior_lookup` / `donor_quality_prior` / `similarity_weighted_vote` | Delivery integrate E1–E4。 |
| P2 | `predict_structure(seq)` | AF3 回退（需轴开启且无 AFDB 结构）。 |
| P2 | `literature_search(rbp_name)` | top-k 摘要增强注释。 |

**表 2（Table 2）：** 与 Delivery BUILD_SPEC 对齐的工具包规范。

**共享约定（Shared conventions）。**

- **标识符（IDs）。** 所有蛋白以 UniProt accession 寻址。  
- **缓存（Caching）。** 长时工具（AF3、literature search）按 \((p^\star,\mathrm{tool})\) 键记忆化；缓存 TTL 可配置。  
- **并发（Concurrency）。** 工具标记为 `read_only` 与 `concurrency_safe`，以便 nanobot 可并行发出。  
- **错误信封（Error envelope）。** 统一 `{status, value | reason, latency_ms}`。

---

## 6 在 nanobot 上的实现（6 Implementation on nanobot）

### 6.1 映射到 nanobot 原语（6.1 Mapping to nanobot Primitives）

| 关注点（Concern） | nanobot 构造（construct） |
|-------------------|---------------------------|
| LLM 提供商与路由 | `nanobot/providers`；在 `~/.nanobot/config.json` 中配置。 |
| 产品控制流 | CLI `nanobot-bio agent\|chat` → `run` / `run_streamed`（主路径）；SDK 草图为辅。 |
| 生物信息学工具 | `nanobot/agent/tools/rbp/` 下 Tool 子类；科学经 App delivery 子进程桥。 |
| 领域知识 / 提示 | Skill SoT `nanobot/skills/rbp-agent/SKILL.md`（+ 可选 `references/`）；sync 到 workspace。 |
| 自演进追踪 | `rbp_eval.nanobot_hooks.RBPTraceHook` → `artifacts/traces/` JSONL。 |
| 超参 | `config/defaults.yaml`（Table 3）；离线 promote 到 `config/evolved.yaml`。 |
| 缓存 / 记忆 | 工具侧记忆化；`session.manager` 对话连续性。 |

### 6.2 仓库布局（6.2 Repository Layout）

```text
nanobot-bio/
  app/                         # 产品 CLI、backends 桥、integrate、dev gates
  nanobot/
    skills/rbp-agent/
      SKILL.md                 # SoT playbook
      references/              # 渐进披露（stages / verdict）
    agent/tools/rbp/           # Toolkit SoT
  workspace/skills/rbp-agent/  # sync 副本（勿手改）
  config/                      # defaults + evolved
  rbp_eval/                    # 离线 Validation Evaluator
  artifacts/{traces,reports,sessions,cache}/
  tests/
```

### 6.3 端到端 SDK 草图（6.3 End-to-End SDK Sketch）

主入口：`nanobot-bio chat` / `nanobot-bio agent --message "..."`。

```python
from nanobot import Nanobot
from rbp_eval.nanobot_hooks import RBPTraceHook

bot = Nanobot.from_config(
    config_path="~/.nanobot/config.json",
    workspace="/path/to/nanobot-bio/workspace",
)
result = await bot.run(
    "这段 RNA 是否与 RBP AATF 相互作用？"
    "RNA: AUGGCU... ; target_uniprot: Q9NY61",
    session_key="rbp:Q9NY61",
    hooks=[RBPTraceHook(out_path="artifacts/traces/run.jsonl")],
)
print(result.content)  # JSON 判定（verdict）
```

---

## 7 自演进机制（7 Self-Evolving Mechanism）

智能体在部署之间通过由 held-out 验证集 \(\mathcal{D}_{\mathrm{val}}\) 驱动的离线循环改进，其中三元组为 \((r,p^\star,y^\star)\)，\(y^\star\in\{0,1\}\) 为真实相互作用标签。

1. **Trace 记录（Trace logging）。** 每次查询运行经 `RBPTraceHook` 写入结构化 trace（工具调用、返回、融合相似度、最终判定）。  
2. **工具归因（Tool attribution）。** 对每个正确解决的查询，从 LLM 的 `supporting_rbps` 字段恢复各工具贡献的支持证据比例；持续低归因的工具成为退役候选。  
3. **权重与阈值重调（Weight & threshold re-tuning）。** 通过在 \(\mathcal{D}_{\mathrm{val}}\) 上最小化校准交叉熵，重拟合视图融合先验与标签阈值。  
4. **工具包扩展（Toolkit expansion）。** 在系统性失败模式上（按查询嵌入聚类），智能体提议新增工具（例如 RNAcompete 衍生 motifs、蛋白–蛋白相互作用网络）；人工审阅并合并。  
5. **缓存提升（Cache promotion）。** 频繁命中的 \((p^\star\to\{p_i\})\) 代理映射被提升到快速缓存，在后续查询上绕过 Stage 1。

---

## 8 默认设计决策（8 Default Design Decisions）

对初始草图中未决的点，我们采用下列默认以使首次实现可控。自演进循环产生证据后，每一项都可再议。

| 问题（Question） | 默认（Default） | 理由（Rationale） |
|------------------|-----------------|-------------------|
| 候选数量 \(N_{\mathrm{cand}}\) | 固定上限 5；LLM 可丢弃相似度低于下限 \(\tau_{\mathrm{drop}}=0.30\) 的条目。 | 五个代理足以平滑单模型噪声而不过度抬高预测器成本；硬下限避免低质量代理拖累均值。 |
| 快速路径阈值（Fast-path threshold） | 严格 UniProt 匹配；或序列一致度 \(\ge 95\%\) 并标注为 “near-known”。 | 严格 ID 无歧义；95% 近匹配是成熟同源截止，并在解释中报告以保持透明。 |
| 结构数据来源（Structure data source） | \(\mathcal{K}\) 优先 AFDB 缓存 + Foldseek；AF3 可选（`axes.use_af3=false` 直至探针绿）；结构失败 ≠ sim `0`。 | 对齐 Delivery HANDOFF；避免目录侧 AF3 冷启动。 |
| 输出粒度（Output granularity） | 四级标签 + **raw** \(\hat{p}\) + 规则 `confidence`。 | 与湿实验筛查对齐；无报告时不宣称 ECE 校准 P(bind)。 |
| 供体聚合（Donor aggregation） | 默认对供体 prob 取 `max`；加权投票为 integrate 工具 / evolve 候选。 | 稳定 MVP；加权均值可在离线 evolve-eval 下再议。 |
| Agent 框架（Agent framework） | nanobot（Python SDK + 自定义 Tool 子类 + 专用 skill）。 | 按团队既有工具链；轻量核心、原生 MCP，并经 hooks 可观测。 |

**表 3（Table 3）：** 开放设计点的默认决策。

---

## 9 评估计划（9 Evaluation Plan）

- **Held-out RBP 划分（Held-out RBP split）。** 将 \(\mathcal{K}\) 划分为 seen（训练）与 held-out（仅评估）RBP，以诚实模拟未见 RBP 设定。  
- **主指标（Primary metrics）。** 将四级标签折叠为二分类后的 AUROC 与 AUPRC；\(\hat{p}\) 上的期望校准误差（ECE）。  
- **消融（Ablations）。** （i）单视图检索（仅序列 / 仅结构 / 仅功能），（ii）固定权重平均 vs LLM 融合相似度，（iii）去掉 Stage 3 LLM 解释（仅数值聚合），（iv）变化 \(N_{\mathrm{cand}}\in\{1,3,5,10\}\)。  
- **定性（Qualitative）。** 抽样 30 条解释，相对底层工具输出人工评定忠实性。

---

## 10 里程碑（10 Milestones）

| 周（Wk） | 里程碑（Milestone） | 负责人（Owner） |
|----------|---------------------|-----------------|
| 1 | 锁定工具接口 schemas（§5） | 双方（Both） |
| 2 | 实现 P0 工具并注册到 nanobot | 工具负责人（Tools owner） |
| 2 | 撰写 rbp-agent skill + 系统提示；SDK 级冒烟测试 | 智能体负责人（Agent owner） |
| 3 | 实现 P1 工具；集成 Stage 1 融合 | 工具负责人（Tools owner） |
| 3 | 实现 RBPTraceHook 与 trace 存储 | 智能体负责人（Agent owner） |
| 4 | 在小验证切片上首次端到端运行；消融 harness | 双方（Both） |
| 5 | 标定阈值，跑完整评估 | 双方（Both） |
| 6 | 自演进循环 v1：在 \(\mathcal{D}_{\mathrm{val}}\) 上重调权重 | 双方（Both） |

---

## 11 开放风险（11 Open Risks）

- **预测器外推（Predictor extrapolation）。** 若目录不能代表 held-out RBP，则即使最佳代理也会无信息。缓解：大声报告低置信；在解释中 surfacing。  
- **LLM 幻觉相似度（LLM hallucinated similarity）。** 融合相似度部分由模型生成；我们通过暴露每视图分解，并用自动化忠实性探测抽查来缓解（Stage 3 评估）。  
- **AF3 成本 / 可用性（AF3 cost / availability）。** 通过对 \(\mathcal{K}\) 缓存结构，以及对靶点优雅的仅序列回退来缓解。

---

*提案正文结束。（End of proposal.）*
