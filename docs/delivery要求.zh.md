# rhobind_agent_delivery 要求文档（中文译本）

> **性质：** 本文是对 `rhobind_agent_delivery/agent/` 内要求类文档的**全文中文翻译**（或收录 delivery 已提供的中文版），**不增删含义、不做摘要改写**。
>
> **权威：** 仍以 delivery 仓内对应原文为准；工具清单与 I/O schema 的机器可读权威为 `agent/tools/registry.json`。
>
> **收录范围：** `HANDOFF.md`、`AGENT_BUILD_SPEC`（含已有 `.zh.md`）、`DESIGN.md`、`SETUP.md`、`README.md`、`tools/` 与子目录 README、`eval/README.md`、`examples/README.md`、`database/README.md`、`database/SOURCES.md`、`backbone/README.md`、`tools/structure/AF3_SETUP.md`，以及 `tools/registry.json` 全文中文对照。
>
> **未收录：** `third_party/alphafold3/` 下 DeepMind 权重/输出法律条款（非 agent 构建规格正文）。
>
> **源树根：** `rhobind_agent_delivery/agent/`（下文路径相对该目录，除非另行标明）。

---

## 目录

1. [HANDOFF.md — 协作交接](#1-handoffmd--协作交接)
2. [AGENT_BUILD_SPEC — 构建规格](#2-agent_build_spec--构建规格)
3. [DESIGN.md — 工具包打包计划](#3-designmd--工具包打包计划)
4. [SETUP.md — 安装部署](#4-setupmd--安装部署)
5. [README.md — 工具包总述](#5-readmemd--工具包总述)
6. [tools/README.md — 工具与 API](#6-toolsreadmemd--工具与-api)
7. [tools/structure/README.md](#7-toolsstructurereadmemd)
8. [tools/structure/AF3_SETUP.md](#8-toolsstructureaf3_setupmd)
9. [tools/sequence/README.md](#9-toolssequencereadmemd)
10. [tools/function/README.md](#10-toolsfunctionreadmemd)
11. [tools/integrate/README.md](#11-toolsintegratereadmemd)
12. [eval/README.md](#12-evalreadmemd)
13. [examples/README.md](#13-examplesreadmemd)
14. [database/README.md](#14-databasereadmemd)
15. [database/SOURCES.md](#15-databasesourcesmd)
16. [backbone/README.md](#16-backbonereadmemd)
17. [tools/registry.json — 工具清单全文对照](#17-toolsregistryjson--工具清单全文对照)

---
## 1. HANDOFF.md — 协作交接

> 源文件：`HANDOFF.md`

# RhoBind Agent — 协作方交接说明

**目标。** 为回答 *"这段 RNA 是否结合 RBP X？"* 的 AI agent 提供工具——当 **X 没有已训练的 head**（新的 RBP）时，通过从相似的已知 RBP 做迁移来回答。

**Agent 做三步**（编排由你们实现；我们提供工具）：
1. **Retrieve（检索）** 相似的已知 RBP（结构 / 序列 / 嵌入 / 结构域 / 功能）。
2. **Predict（预测）** — 用这些相似 RBP 的 RhoBind head 在查询 RNA 上跑分。
3. **Integrate（整合）** — 按相似度 + 先验加权预测 → 一个可解释的判定（verdict）。

这建立在我们的 leave-one-RBP-out（留一 RBP）研究之上：最佳的相似 RBP head ≈ 该 RBP 自己的 head，且 ESM-C 相似度是最可靠的迁移信号。

## 我们交付的内容（均已构建并验证）

| 部件 | 位置 |
|---|---|
| **24 个工具**，统一 JSON 入/出，自描述 | `tools/registry.json` + `tools/<category>/<name>.py` |
| **知识库**（238 个 RBP：registry、嵌入、结构、相似度、LOO transfer、结合 peaks） | `database/`（小文件）+ 运行时副本在 **pc157** `…/agent_db/` |
| **已训练预测器**（K562 + HepG2 checkpoints） | `../release/`（由 `rhobind_predict` 引用） |
| **本地 AlphaFold3**（预测 + AFDB/AF3 共识、置信度） | `tools/structure/` + `third_party/alphafold3/`（[`AF3_SETUP.md`](tools/structure/AF3_SETUP.md)） |

## 你们需要构建的

**Agent 循环** + **两个 LLM 触点**：（1）对功能文本的推理（`uniprot_annotation` / `literature_retrieval` 给出干净 JSON），以及（2）最终整合/解释（`integrate/` 工具交给你们一张证据表 + 一个确定性基线分数供解释）。

## 工具如何工作

每个工具既是 CLI，也是可 import 的 `run(payload)->dict`：
```bash
python tools/sequence/esm_similarity.py --json '{"sequence":"MD...","encoder":"esmc","device":"cuda","top_k":10}'
```
工具通过环境变量读取运行时 DB（默认 = pc157 路径；换机时改指向）。每个 registry 条目列出 `network`、`gpu` 与 `est_runtime`。

## 环境（conda，在 pc157 上）
- `protein_embed` — foldseek + ESM 工具  ·  `rna` — mmseqs 工具  ·  `rhobind` — 预测器  ·  `af3` — AlphaFold3（均由 `setup_envs.sh` 创建）。
- 纯 Python 工具（功能查询、整合、resolve、RNA 预处理、RCSB/EuropePMC）可在任意环境运行。

## 安装（一键 — 含 AF3 权重等全部内容均已打包，仅供内部使用）
```bash
source agent/setup.sh        # 相对本包设置全部环境变量
bash   agent/setup_envs.sh    # 一次性：创建全部 conda env（protein_embed, rna, rhobind, af3）
```
完整说明 + conda env 列表：[`SETUP.md`](SETUP.md)。

## 从这里开始
1. [`SETUP.md`](SETUP.md) — 设置 env + envs（见上）。
2. `tools/registry.json` — 工具目录。
   - 对整条流水线做冒烟测试：`bash agent/examples/run_example.sh`（黄金输出见 `agent/examples/README.md`）。
3. [`AGENT_BUILD_SPEC.md`](AGENT_BUILD_SPEC.md) — 详细构建规格（流水线、payload、envs、完整示例）。
4. [`DESIGN.md`](DESIGN.md) — 设计理由与科学依据。  ·  `eval/` — 用于调选择/权重的 val harness。

## 开放决策（由你们决定）
新 RBP 的输入模态（accession / 序列 / 结构 — 全部支持）；如何融合各检索轴以及如何加权第 3 步（在 `eval/` val 集上调）；abstention（弃权）阈值。

---
## 2. AGENT_BUILD_SPEC — 构建规格

> 源文件：`AGENT_BUILD_SPEC.md`；本节**全文收录** delivery 自带中文版 `AGENT_BUILD_SPEC.zh.md`（不改写）。

# RhoBind Agent — 构建规格（面向实现编排的 coding agent）

在已封装工具之上实现编排逻辑。工具本身无状态；**agent 负责控制流、检索融合，以及两个 LLM 步骤**。工具清单与 I/O schema 以 `tools/registry.json` 为准。

---

## 1. 调用约定

每个工具有两种等价入口：

```bash
python tools/<category>/<name>.py --json '<payload-json>'   # CLI，向 stdout 打印 JSON
```

```python
import sys; sys.path.insert(0, "tools/<category>")
from <name> import run; out = run(payload_dict)              # 进程内调用
```

- 标识符统一：`{alias, uniprot}`（例如 `PTBP1 / P26599`）；队列（cohort）为 `K562 | HepG2`。
- 共享返回类型：`RbpHit {alias, uniprot, score, metric, rank}`；`Prediction {alias, prob, head_index, cohort}`。
- 从 `tools/registry.json` 发现工具与参数（字段：`category, status, network, gpu, est_runtime, input_schema, output_schema`）。`status:ready` = 可运行。

## 2. 运行时数据 + 环境变量（默认 = pc157）

工具路径由 `tools/_common.py` 解析，均可覆盖以便换机部署：

| 环境变量 | 默认值（pc157） | 使用者 |
|---|---|---|
| `AGENT_DB` | `/workspace/jmwang/rna/interaction/agent_db` | 全部 |
| `RBP_REGISTRY` | `$AGENT_DB/registry/rbp_registry.json` | 大多数 |
| `EMB_BANK` | `$AGENT_DB/embedding_bank` | esm_similarity |
| `FOLDSEEK_DB` | `$AGENT_DB/foldseek_db/refs` | struct_similarity_foldseek |
| `SEQ_DB` | `$AGENT_DB/seq_db/refs` | protein_seq_similarity |
| `PEAKS_DB` | `$AGENT_DB/peaks_db/peaks` | rna_blastn |
| `AFDB_DIR` | `…/rbp_proteins_260417/structures/afdb` | structure_fetch, consensus |
| `TRANSFER_DIR` | `$AGENT_DB/transfer` | transfer_prior_lookup |
| `USALIGN` | `$AGENT_DB/bin/USalign` | struct_align_usalign |
| `AF3_DIR`,`AF3_PARAMS`,`AF3_PYTHON` | pc101/pc157 上的 AF3 安装 | structure_predict_af3 |
| `RHOBIND_RELEASE` | `../release/rhobind_release_v1` | rhobind_predict |

## 3. 每个工具对应的 conda 环境（在正确 env 中运行）

| 环境 | 工具 |
|---|---|
| `protein_embed`（foldseek, esm, transformers） | struct_similarity_foldseek, struct_align_usalign, structure_consensus, esm_embed, esm_similarity |
| `rna`（mmseqs） | protein_seq_similarity, rna_blastn |
| `af3`（通过 `AF3_PYTHON` 调用） | structure_predict_af3（colabfold_msa 仅用普通 urllib） |
| `rhobind`（torch + transformers；依赖见 release/requirements.txt） | rhobind_predict |
| 任意 python3（+numpy） | resolve_rbp, structure_fetch, pymol_util, go_pfam_lookup, function_category, uniprot_annotation, pdb_metadata, literature_retrieval, domain_architecture, rna_preprocess, 全部 `integrate/` |

`esm_embed` / `esm_similarity` 接受 `"device": "cuda"|"cpu"`。各工具的 GPU / 网络标志见 registry。

## 4. 标准流水线（Canonical pipeline）

```
resolve_rbp(query) -> {alias, uniprot, in_panel}
if in_panel:                     # 已知 RBP：直接用其自身 head
    windows = rna_preprocess(rna)
    pred = rhobind_predict(rna=windows, rbps=[alias], cohort)
    return verdict(pred)         # 无需 transfer

# --- 新 RBP：表征 ---
structure = structure_fetch(uniprot) or structure_predict_af3(sequence)        # 可选
ann       = uniprot_annotation(uniprot)        # 功能文本 + Pfam + RBD 类型（★ LLM）

# --- 多轴检索 donor（可并行；各自返回 RbpHit[]）---
hits_seq    = protein_seq_similarity(sequence)
hits_emb    = esm_similarity(sequence, encoder="esmc", device, uniprot)         # 最佳信号
hits_struct = struct_similarity_foldseek(structure.pdb_path)                    # 有结构时
hits_dom    = domain_architecture(sequence|alias)                              # RBD 重叠
# 可选精修：struct_align_usalign(query_pdb, targets=top-k aliases)
donors = fuse(hits_emb, hits_struct, hits_seq, hits_dom)   # 你们的排序/权重（在 eval/ 上调）
abstain = confidence_abstain(hits_emb)        # OOD 防护

# --- 用 donor 的 head 做预测 ---
windows = rna_preprocess(rna)["windows"]
preds   = rhobind_predict(rna, rbps=[d.alias for d in donors], cohort)          # Prediction[]
# 可选 RNA 侧佐证：rna_blastn(rna)

# --- 整合（第 3 步）---
tprior  = transfer_prior_lookup(target=alias, donors=[...])      # LOO 实测（10 个 target）
quality = donor_quality_prior(donors, cohort)                    # donor head 的 AUPRC
score   = similarity_weighted_vote(preds, hits=donors,
                                   transfer_priors=tprior, donor_quality=quality)
# -> 确定性基线分数 + 每个 donor 的贡献分解
verdict = LLM_integrate(evidence_table, score, abstain, ann)     # ★ LLM 最终答案
```

## 5. 两个 LLM 触点

- **★ 功能推理：** 将 `uniprot_annotation`（可选再加 `literature_retrieval`、`pdb_metadata`）的 JSON——字段如 `function`、`go`、`rbd_type`、`function_category`——交给 LLM，比较 target 与候选 donor 的功能。不要自己爬网页；工具已返回干净字段。
- **★ 最终整合：** 用 `similarity_weighted_vote.contributions`（similarity、prob、transfer_prior、donor_quality）+ `confidence_abstain` + 基线 `score` 拼成按 donor 的 **证据表（evidence table）**；LLM 输出校准后的是/否 + 理由。若 `abstain.confident == false`，应弱化结论（hedge）。

## 6. 置信度

- **结构可信度：** `structure_predict_af3` 返回 `mean_plddt`、`structured_core_plddt`、`region_plddt`（可将 RBD 的 `regions` 从 `uniprot_annotation.features` / `domain_architecture` 传入）、`ptm`、`fraction_disordered`、`has_clash`；`structure_consensus` 协调 AFDB 与 AF3。
- **Donor 可信度：** `donor_quality_prior`（head 的 val-AUPRC）。**Transfer 可信度：** `transfer_prior_lookup`。
- **OOD：** `confidence_abstain`（按 metric 的相似度阈值，可调）。

## 7. 自演进 / 调参

使用 `eval/`（广义 LOO：隐藏某个已知 RBP 的 head，跑候选策略，与 `database/transfer/loo_summary.csv` 中的 own-head 上限对比打分）。在此调融合权重与 abstention 阈值；新增工具 = 在 `registry.json` 加一条 + 写 adapter。

## 8. 完整示例（新 RBP，按 accession）

可运行的端到端 demo 与黄金输出：`agent/examples/run_example.sh`（见 `agent/examples/README.md`）。

```bash
# 1 resolve
python tools/utility/resolve_rbp.py --json '{"query":"Q9NZI8"}'        # -> IGF2BP1, in_panel
# （若是新 RBP）2 用嵌入检索
python tools/sequence/esm_similarity.py --json '{"sequence":"M...","encoder":"esmc","device":"cuda","top_k":10,"uniprot":"Q9NZI8"}'
# 3 用 top donors 对 RNA 预测
python tools/backbone/rna_preprocess.py --json '{"rna":"ACGU...","window":128,"stride":64}'
python tools/backbone/predict_api.py --json '{"rna":"...","rbps":["ELAVL1","PCBP1"],"cohort":"K562"}'
# 4 整合
python tools/integrate/similarity_weighted_vote.py --json '{"predictions":[...],"hits":[...]}'
```

## 9. 注意事项（Caveats）

- **队列：** K562（118 个 head）+ HepG2（85）。Donor 必须在所选 cohort 中有 head（见 `registry[uniprot].cohorts` / `head_index`）。
- AF3 权重已内部打包（`af3_assets/`，见 `SETUP.md`）；`rna_blastn` 需要预构建的 peaks DB；SaProt 嵌入需要结构。网络工具（`uniprot_annotation`、`pdb_metadata`、`literature_retrieval`、`colabfold_msa`）离线时可跳过。
- 各检索分数虽都是 [0,1] 相似度，但 **不同 metric 尺度不同** —— 融合前需要归一化。


---
## 3. DESIGN.md — 工具包打包计划

> 源文件：`DESIGN.md`

# RhoBind Agent Toolkit — 打包计划

**读者：** 正在构建 agent 框架的协作方。
**我们的交付物：** 一套已打包的 *工具 + 数据索引 + 参考实现*，具有统一接口。我们 **不** 构建 agent/LLM 编排——我们把 agent 所需的每项能力做成可调用且自描述的。

---

## 0. 框架说明 — agent 做什么，以及工具服务的那一个核心想法

Agent 回答 *"这段 RNA 是否与 RBP X 相互作用？"*，针对 **X 没有已训练 head**（新的 RBP）。机制（来自框架图）：

1. **Retrieve（检索）** 从我们已训练 panel 中最相似的 RBP（结构 / 序列 / 功能相似度）。
2. **Predict（预测）** 用我们的已训练模型，在查询 RNA 上运行 **相似 RBP 的 heads** → 得到概率。
3. **Integrate（整合）** 将 prob × 相似度（+ 一个校准先验）→ 单个可解释判定。

**科学基础已经确立。** 我们的 leave-one-RBP-out 实验 *就是* 这条流水线的离线度量：隐藏某个 RBP 的 head，用其余 117 个来预测它。工具包应编码的发现：
- 当存在相关 RBP 时，**最佳外来 head ≈ 自身 head**（例如 FXR2←FMR1 0.745 vs 0.768；EEF2←APEX1 0.698 = 0.698）。因此第 2/3 步是站得住的。
- **ESM-C 嵌入余弦** 是迁移质量最一致（但仍偏弱）的预测因子；原始序列一致度与结构 lDDT 更嘈杂。→ agent 应对各模态加权，而不是信任任一单一模态。
- 多数迁移信号存在于 **共享编码器** 中，因此即使中等相似的 donor 也有帮助；但 *建模很差* 的 donor（自身 head AUPRC 低）应被降权。

下文的一切都是为了让 agent 能够执行并校准上述三步。

---

## 1. 打包约定（让每个工具对 agent 看起来完全一样）

- **每个工具 = 带 JSON 入 / JSON 出的 CLI + 一层薄 Python 函数。** 同一工具，两种入口（子进程或 import）。
- **中心 `tools/registry.json`** — 每个工具一条：`{name, category, summary, input_schema, output_schema, side_effects, network: bool, gpu: bool, est_runtime, deps}`。Agent 读它来发现能力。**这就是自演进挂钩**：新增工具 = 新增 registry 条目 + adapter；权重/选择可在 val 集上调。
- **处处使用规范标识符：** 每个 RBP 是 `{alias, uniprot}`（例如 `PTBP1 / P26599`）；每个队列是 `K562 | HepG2`。一套共享的 `RbpHit` schema（`alias, uniprot, score, metric, rank`）与一套 `Prediction` schema（`alias, prob, head_index, cohort`），以便输出可组合。
- **标记** `network`（在线 vs 离线）、`gpu`，以及每个工具的粗略运行时间，以便 agent 规划成本（也便于无头/cron 运行避开网络工具）。

---

## 2. 共享数据产物 — 检索骨干（大多 READY）

| 产物 | 是什么 | 状态 |
|---|---|---|
| **`rbp_registry.json`** | THE 索引：每个可用 RBP 一条记录 = alias、uniprot、cohort(s)、cluster id+label、Pfam domains、GO slim、功能类别、RBD 类型、训练规模、**每个 RBP 的 val/test AUPRC/AUROC（head 可靠性先验）**、结构/序列/嵌入路径 | **assemble（组装）**（全部输入已存在） |
| **Embedding banks（嵌入库）** | ESM2 650M、ESM-C 600M、SaProt 650M 均值池化向量，238 个蛋白 | **ready**（每个蛋白一个 .pkl → 重打包为一个矩阵 + id 列表） |
| **Foldseek 结构 DB** | 238 个 AFDB 模型的 3Di 索引库，用于快速结构搜索 | **build index（建索引）**（结构 + foldseek 已就绪） |
| **Sequence DB（序列库）** | mmseqs/BLAST 索引的 238 条 UniProt 规范序列 | **build index（建索引）**（序列已就绪） |
| **成对相似度矩阵** | seq-id、foldseek lDDT/TM/fident、ESM2/ESM-C/SaProt cosine | **118 已 ready**；扩展到 238 |
| **已知 motif 库** | 每 cluster 的 k-mer motifs（PWM 可选），用于 RNA 侧匹配 | **partial（部分）**（cluster motifs 已就绪；每 RBP 可选） |
| **LOO transfer 矩阵 + 校准** | 10×117 实测 donor→target transfer AUPRC；第 3 步先验与 abstention 阈值的基础 | **ready**（我们的输出） |

---

## 3. 按类别的工具（图中的框 + 增补）

图例 — **[R]** ready/包装已有，**[B]** 需构建，**[★]** 面向 LLM。

### A · 结构相关
- **A1 `structure_fetch`** [R] — UniProt acc → AFDB 模型（本地 238，否则下载）。
- **A2 `structure_predict_af3`** [B] — 序列 → 预测结构（当 AFDB 缺失时）。包装 AF3-server skill。*在线、慢 → 仅作回退。*
- **A3 `struct_similarity_foldseek`** [R] — 查询结构 vs 参考库 → 排序的 TM/lDDT `RbpHit`s。（我们已跑过。）
- **A4 `struct_align_usalign`** [B] — 对来自 A3 的 top-k 对给出精确 TM-score（精修）。
- **A5 `pymol_util`** [R] — 从结构取序列、清洗、可选渲染。

### B · 序列相关
- **B1 `protein_seq_similarity`** [R] — 新 RBP 序列 vs 序列库 → %id、e-value、排序。mmseqs（已有）；可选 phmmer 做远端同源。
- **B2 `esm_embed` + `esm_similarity`** [B] — 嵌入新序列（ESM2/ESM-C/SaProt）→ 与 bank 的 cosine → 排序。*Banks 已就绪；需要按需嵌入服务（GPU）。*
- **B3 `domain_architecture`** [B, **高价值**] — 新序列 → Pfam/InterPro domains → 对 refs 的 RBD 感知结构域重叠相似度。RBP 特异性由结构域驱动（RRM/KH/zinc-finger），因此这常常比整链相似度更有预测力。
- **B4 `rna_blastn`** [B, 可选] — *RNA 侧*：查询 RNA vs 已知结合 peaks / 转录组 → 与已知位点的直接序列匹配。

### C · 功能相关（面向 LLM ★）
- **C1 `uniprot_annotation`** [R,★] — acc → 结构化 JSON：功能文本、GO、keywords、domains、RBD 类型。（Fetcher 已有；返回干净 JSON，不是 HTML。）
- **C2 `pdb_metadata`** [B,★] — acc/结构 → PDB 条目、蛋白–RNA 复合物、结合配体。
- **C3 `literature_retrieval`** [B,★] — RBP 名称 → PubMed/Europe PMC abstracts/snippets，供功能推理。
- **C4 `go_pfam_lookup`** [R] — 对参考 RBP 的本地注释查询（离线）。
- **C5 `function_category`** [R] — RBP → splicing/stability/translation/…（分配表已存在）。

### D · 预测 — 第 2 步（READY，只需包装）
- **D1 `rhobind_predict`** [R] —（RNA 序列或 FASTA、RBP alias 列表、cohort）→ 用该 RBP 的 head 给出每个 RBP 的 `Prediction`。将 `infer.py` 包装为基于已发布 checkpoints 的批量 JSON API。
- **D2 `rna_preprocess`** [B] — 任意 RNA → 128-nt 窗口（切分 + 聚合策略：窗口上 max/mean）、U/T + 链处理。因为模型对 ≤128-nt 窗口打分，而不是整条转录本。

### E · 整合与校准 — 第 3 步（构建，源自 LOO）
- **E1 `similarity_weighted_vote`** [B] — {donor: prob} × {donor: similarity} → 聚合分数 + 每个 donor 的贡献。确定性基线，LLM 可以覆盖且必须解释。
- **E2 `transfer_prior_lookup`** [B] — target↔donor → 来自 LOO 矩阵的经验迁移可靠性，从而对迁移差的 donor 降权。
- **E3 `confidence_abstain`** [B] — OOD 检查：若最大相似度 < 由 LOO 导出的阈值 → 低置信/弃权标志。
- **E4 `donor_quality_prior`** [R] — 来自 registry 的每 RBP head 可靠性（val AUPRC），从而对 *相似但建模很差* 的 donor 降权。

---

## 4. 两个 LLM 触点 — 我们交给模型什么

- **★ 功能推理（C1/C3）：** 返回 *干净的结构化 JSON* — 预提取的 RBD 类型、GO-slim 术语、keywords、一段功能摘要 — 不是原始网页。LLM 比较 target 与候选功能，无需爬取。
- **★ 最终整合（E1–E4）：** 交给 LLM 一张紧凑的 **证据表** — 每个 donor：各模态相似度、预测 prob、transfer prior、donor quality，外加确定性基线答案与弃权标志。LLM 产出校准后的、人类可读判定（"Yes, most likely, because …"）。

---

## 5. 自演进支持（交付这些，以便工具包可增长）

- **Val 集 + eval harness。** 复用我们广义化的 LOO 协议：把每个 held-out RBP 当作"新的"，隐藏其 head，让候选的选择+整合策略恢复一个预测，相对 own-head 上限打分。这度量端到端 agent 质量以及每个工具/权重的边际价值——正是图中"扩展工具包 / 在 val 集上调权重"的循环。
- **由 registry 驱动的增长。** 新工具 = registry 条目 + adapter；选择权重与弃权阈值是在 val 上调的参数。Agent 中没有任何东西硬编码到今天的工具列表。

---

## 6. 给你们 / 协作方的决策（真正的分叉）

1. **新 RBP 输入模态** — 接受 `{UniProt acc | 原始蛋白序列 | 基因名 | 结构文件}`？ *建议：全部；acc 为主，seq 是驱动 B1/B2/B3 的回退。*
2. **结构来源** — 仅 AFDB vs 按需 AF3。 *建议：AFDB/UniProt 优先，仅当无模型时 AF3 回退（AF3 慢 + 在线）。*
3. **序列工具** — mmseqs（快，手头有）vs BLASTp vs phmmer。 *建议：默认 mmseqs + 可选 phmmer 做远端同源。*
4. **参考 panel 范围** — 238 个 K562∪HepG2 蛋白，还是更广？ *建议：交付 238；把 registry 设计成可扩展。*
5. **交付形态** — CLI+JSON 与 Python 两者都要（推荐）；外加 conda `environment.yml` 与可选 Docker 镜像给协作方。

---

## 7. 构建清单与分阶段

**Phase 0 — 组装已就绪内容（低工作量）：**
`rbp_registry.json` · embedding-bank 重打包 · foldseek + mmseqs 索引 · 相似度矩阵 → 238 · `rhobind_predict` API（包装 infer.py） · `go_pfam_lookup` / `function_category` / `uniprot_annotation`。

**Phase 1 — 包装/构建核心工具：**
`esm_embed` 服务 · `domain_architecture` · `pdb_metadata` · `literature_retrieval` · `rna_preprocess` · `similarity_weighted_vote` + `transfer_prior_lookup` + `confidence_abstain` · `struct_align_usalign` · `structure_predict_af3` 包装。

**Phase 2 — 自演进基础设施：**
val harness（广义 LOO）· 校准后的 transfer 先验 + 弃权阈值 · 工具价值消融报告。

**已在手头（无需构建）：** 已训练预测器 + 2 个 checkpoints、238 嵌入 ×3 编码器、238 AFDB + 197 PDB 结构、Pfam/GO/功能类别表、每 cluster motifs、LOO transfer 矩阵、mmseqs/foldseek 二进制、AF3 与 HDOCK skills。

---

### 一句话总结
打包一套覆盖三种检索模态（结构 A1–A5、序列 B1–B4、功能 C1–C5）的 **统一 JSON 工具包**、**已训练预测器**（D1–D2），以及 **LOO 校准的整合层**（E1–E4）——全部由单个 `rbp_registry.json` 与 `tools/registry.json` 索引，并带 val harness 以便 agent 自演进。约 70% 的数据已产出；工作是包装、建索引与整合/评估层。

---

## v2 候选（内部说明 — 尚未进入 agent registry）

在模型上基准其价值之前先搁置：
- **RNA 侧 motif 工具**（来自我们 cluster k-mer motifs 的 `rbp_motif` + `rna_motif_scan`）— 可解释的特异性信号。
- **`score_calibration`** — 每个 head 的背景百分位，使不同 donor 的 probs 可比。
- **`prediction_saliency`** — attention-pool 权重作为每个核苷酸的重要性，用于解释。

这些曾纳入范围但从 v1 撤下，因为需要先在 RhoBind 上验证。

---
## 4. SETUP.md — 安装部署

> 源文件：`SETUP.md`

# RhoBind Agent — 安装（内部实验室部署）

交付包的一键安装。全部数据、预测器与 AF3 权重均已包含（仅供内部使用 — 请勿对外分享 AF3 权重）。

## 包布局
```
rhobind_agent_delivery/
  agent/        工具、registry、文档、AF3 代码、安装脚本
  agent_db/     运行时 DB（registry、embedding/foldseek/seq/peaks DB、USalign、transfer）
  reference/    AFDB 结构 + UniProt 序列
  release/      已训练预测器（checkpoints + 代码）
  af3_assets/   AF3 权重（af3.bin.zst）+ ccd.pickle   ← 仅内部
```

## 1. 设置环境变量（每个 shell 一行）
```bash
source agent/setup.sh
```
设置 `AGENT_DB`、`RBP_PROTEINS`、`RHOBIND_RELEASE`、`AF3_DIR`、`AF3_PARAMS`、
`USALIGN`、`PEAKS_DB`，… 全部相对本包 — 无需编辑。

## 2. Conda 环境 — 一次性全部创建（一条命令）
```bash
bash agent/setup_envs.sh
```
根据打包的规格（`agent/envs/`）+ release 的 requirements 创建 **全部四个** env，并运行 AF3 安装。幂等（已存在的 env 会跳过）。

| Env | 提供 | 工具 |
|---|---|---|
| `protein_embed` | foldseek、esm、transformers、torch | foldseek/USalign、esm_embed/similarity、structure_consensus |
| `rna` | mmseqs | protein_seq_similarity、rna_blastn |
| `rhobind` | torch、transformers（DNABERT-2）— 来自 `release/requirements.txt` | rhobind_predict |
| `af3` | AlphaFold3（在此构建） | structure_predict_af3 |
| 以上任一（有 numpy） | — | resolve、功能查询、integrate、rna_preprocess、RCSB/EuropePMC |

> GPU 构建（torch/CUDA、foldseek/mmseqs）钉在我们的机器上；在不同 CUDA/架构上，更换 torch wheel（`release/requirements.txt`），并且若 conda 无法求解，则从 bioconda 重装 foldseek/mmseqs。

## 3. 仅 AlphaFold3（若你跳过了 setup_envs.sh）
```bash
bash agent/setup_af3.sh
```
创建 `af3` env，构建 C++ 扩展，放置打包的 CCD；权重已在 `af3_assets/`。（结束时打印 ubiquitin 测试命令。）

## 4. 冒烟测试（端到端，黄金输出）
```bash
bash agent/examples/run_example.sh        # 加 'cpu' 可在无 GPU 时运行
```
在样例案例上运行 resolve → esm_similarity → domain_architecture → rhobind_predict → integrate（把 PTBP1 当作"新" RBP）。期望输出见 `agent/examples/README.md`；
若各步匹配且 PTBP1 的 own-head AUPRC 复现 0.9311，则部署良好。

---

## 5. README.md — 工具包总述

> 源文件：`README.md`

# RhoBind Agent — 面向新 RBP 推断的工具包

> **交接：** 协作方从 [`HANDOFF.md`](HANDOFF.md) 开始（简明概览）；
> 构建框架的 coding agent 使用 [`AGENT_BUILD_SPEC.md`](AGENT_BUILD_SPEC.md)
>（流水线、payload、envs、完整示例）。

支持包，供回答 *"这段 RNA 是否与 RBP X 相互作用？"* 的 AI agent 使用——当 **X 没有已训练 head**（新的 RBP）时。Agent 检索最相似的已知 RBP，在查询 RNA 上运行它们的 RhoBind heads，并按相似度整合结果。完整理由与科学基础（我们的 leave-one-RBP-out 验证）见 [`DESIGN.md`](DESIGN.md)。

本文件夹保存 **新增的** agent 支持组件。它 **不** 修改现有仓代码，也不修改 [`../release/`](../release) 中已交付物。

## 三大支柱

| # | 支柱 | 文件夹 | 是什么 |
|---|--------|--------|------------|
| 1 | **Database（数据库）** | [`database/`](database) | *已知* RBP panel 的冻结知识库 — 序列、结构、嵌入、注释、相似度矩阵、transfer 先验。Agent 对着它搜索的只读参考。 |
| 2 | **Tools & APIs（工具与 API）** | [`tools/`](tools) | 作用于 *新* RBP / RNA 的主动能力 — 做嵌入、预测结构、搜数据库、挖文献、整合证据。统一 JSON 入/出 + agent 读取的 `registry.json`。 |
| 3 | **Backbone（骨干）** | [`backbone/`](backbone) | 独立的 RhoBind 预测器（已交付物）包装为供 agent 使用的预测 API。 |

外加 [`eval/`](eval) — 自演进的 val harness，以便在 held-out 数据上增长与加权工具包。

## 查询如何流动

```
新 RBP（acc / seq / 结构）+ RNA
        │
        ▼
 [tools] 嵌入 / 折叠 / 注释新 RBP          ──搜索──▶  [database]  ──▶ 排序的相似已知 RBP
        │                                                                              │
        ▼                                                                              ▼
 [tools] rna_preprocess  ──────────────────────────────────────▶  [backbone] 用 donors 的 heads 跑 RNA → probs
        │                                                                              │
        ▼                                                                              ▼
 [tools/integrate] 相似度 × prob × transfer-prior  ◀── [database] transfer 先验、donor 质量
        │
        ▼
   证据表  ──▶  (LLM)  ──▶  可解释判定
```

## 构建状态一览

- **此处已就绪 / 已暂存：** 注释（Pfam、GO、功能类别）、成对相似度矩阵、LOO transfer 矩阵、cluster 分配、RBP 元数据清单。
- **在远端，待建索引：** 238 条 UniProt 序列、238 AFDB + 197 PDB 结构、238×3 ESM2/ESM-C/SaProt 嵌入（见 [`database/SOURCES.md`](database/SOURCES.md)）。
- **待构建：** [`tools/`](tools) 中的主动工具（嵌入服务、结构/序列搜索包装、功能抓取、整合层）以及 [`eval/`](eval) harness。

## 约定

- 每个 RBP 用 `{alias, uniprot}` 标识（例如 `PTBP1 / P26599`）；每个队列是 `K562 | HepG2`。
- 每个工具是带 `--json` 入/出的 CLI **并且** 是可 import 的 Python 函数，描述于 [`tools/registry.json`](tools/registry.json)。
- 运行时重数据在 `pc157`；本树保存 schemas、小的派生产物，以及在那里组装完整数据库的构建/抓取脚本。

---

## 6. tools/README.md — 工具与 API

> 源文件：`tools/README.md`

# 支柱 2 — 工具与 API（作用于新 RBP / RNA）

Agent 调用的主动能力。每个工具读取 [database](../database) 和/或外部服务并返回结构化 JSON。工具从不嵌入 agent 逻辑 — 它们是无状态函数；规划由 agent（协作方）完成。

## 约定（每个工具都遵循）

- **两种入口，同一行为：** CLI（`python tools/<cat>/<name>.py --json '<in>'`）与可 import 的 `run(payload: dict) -> dict`。
- **自描述：** 每个工具在 [`registry.json`](registry.json) 中有一条，含 `input_schema`、`output_schema`、`category`、`status`、`network`、`gpu`、`est_runtime`。新增工具 = 加一条 + adapter → 这就是 **自演进** 挂钩（agent 从 registry 发现工具，而不是从代码）。
- **共享类型：** 检索工具返回 `RbpHit` 列表 `{alias, uniprot, score, metric, rank}`；预测器返回 `Prediction` `{alias, prob, head_index, cohort}`。标识符始终是 `{alias, uniprot}`。
- **离线安全标志：** `network: true` 的工具（AF3、UniProt、PDB、文献）在无头/cron 上下文中被跳过；其余全部离线对着 DB 运行。

## 类别（文件夹）

| 文件夹 | 工具 | 对应图中 |
|---|---|---|
| [`structure/`](structure) | `structure_fetch`、`structure_predict_af3`、`struct_similarity_foldseek`、`struct_align_usalign`、`pymol_util` | 结构相关（AF3、pymol、USalign） |
| [`sequence/`](sequence) | `protein_seq_similarity`（mmseqs）、`esm_embed`、`esm_similarity`、`domain_architecture`、`rna_blastn` | 序列相关（BLASTn、ESM） |
| [`function/`](function) | `uniprot_annotation`★、`pdb_metadata`★、`literature_retrieval`★、`go_pfam_lookup`、`function_category` | 功能相关（Literature、UniProt、PDB） |
| [`integrate/`](integrate) | `similarity_weighted_vote`、`transfer_prior_lookup`、`confidence_abstain`、`donor_quality_prior` | 第 3 步整合（LOO 校准） |

★ = 为 LLM 产出文本（功能推理）；返回干净结构化 JSON，不是原始页面。

预测器（`rhobind_predict`、`rna_preprocess`）与骨干放在一起 — 见 [`../backbone`](../backbone) — 并且也列在 `registry.json` 中以便统一访问。

每个工具的目的、I/O 契约与 ready-vs-build 状态见 [`../DESIGN.md`](../DESIGN.md) §3。

---
## 7. tools/structure/README.md

> 源文件：`tools/structure/README.md`

# tools/structure

结构相关工具（图：AF3 / pymol / USalign）。契约见 [`../registry.json`](../registry.json)，理由见 [`../../DESIGN.md`](../../DESIGN.md) §3.A。

| 工具 | 状态 | 说明 |
|---|---|---|
| `structure_fetch.py` | ✅ 已实现 | acc → 从 DB 取 AFDB 模型，否则下载 |
| `struct_similarity_foldseek.py` | ✅ 已实现 | 查询 vs `database/foldseek_db` → 排序 hits |
| `struct_align_usalign.py` | ✅ 已实现 | 精确 TM（US-align；foldseek 回退）精修 top-k |
| `structure_predict_af3.py` | **ready（本地 AF3）** | 序列 → 本地 AlphaFold3 结构；MSA 经 ColabFold |
| `colabfold_msa.py` | **ready** | 序列 → 经 ColabFold MMseqs2 API 的 a3m MSA（为 AF3 清洗） |
| `structure_consensus.py` | **ready** | AFDB + AF3 → TM 一致性 + CA-pLDDT/pTM → 选定结构 |
| `pymol_util.py` | ✅ 已实现 | 从结构取序列、清洗、渲染 |

## 本地 AlphaFold3

AF3 作为 **本地** 预测器集成（不是 web server）：`structure_predict_af3` 从 ColabFold MMseqs2 API 获取 MSA，构建 AF3 输入 JSON，并在 [`../../third_party/alphafold3`](../../third_party/alphafold3) 中以 `--norun_data_pipeline` 运行已 vendored 的 AF3（无需本地遗传数据库）。然后 `structure_consensus` 比较 AF3 模型与 AFDB 模型并择一。

**安装（权重、环境、部署）：[`AF3_SETUP.md`](AF3_SETUP.md)。** 权重 **未** 随（公开）包分发 — 将 `AF3_PARAMS` 指向 `af3.bin.zst`。

已验证：ubiquitin 折叠到 mean pLDDT 91.16 / ranking 0.84；foldseek TM self=1.0，PTBP1·FXR2=0.23；AFDB/AF3 对 PDB 与 mmCIF 的 pLDDT 解析。

---

## 8. tools/structure/AF3_SETUP.md

> 源文件：`tools/structure/AF3_SETUP.md`

# 本地 AlphaFold3 — 安装与部署

Agent 对需要预测结构的新 RBP **在本地运行 AlphaFold3**，MSA 由 **ColabFold MMseqs2 API** 提供（因此不需要本地遗传数据库）。本文说明打包了什么、权重放哪里、如何构建环境，以及如何 redeploy 到另一台工作站。

## 打包了什么 / 没打包什么

| 组件 | 是否打包？ | 位置 / 如何获得 |
|---|---|---|
| AF3 源代码 | **是** | [`../../third_party/alphafold3`](../../third_party/alphafold3)（DeepMind 仓，减去下列项） |
| 我们的包装 | **是** | `structure_predict_af3.py`、`colabfold_msa.py`、`structure_consensus.py` |
| 模型权重（`af3.bin.zst`，约 1 GB，受控） | **是（内部）** | 在 `af3_assets/alphafold_param/`；`setup.sh` 将 `AF3_PARAMS` 指向它。**仅内部实验室使用** — 见 `WEIGHTS_TERMS_OF_USE.md` / `WEIGHTS_PROHIBITED_USE_POLICY.md`；请勿再分发。 |
| `ccd.pickle`（化学组分，约 471 MB） | **是** | 在 `af3_assets/`；`setup_af3.sh` 放置它（因此不需要 `build_data` / 网络）。 |
| 遗传数据库（数百 GB） | **否** | 不需要 — MSA 来自 ColabFold。 |
| `alphafold_bin`（hmmer） | **否** | 仅当你运行 AF3 *自己的* 数据流水线而不是 ColabFold 时才需要。 |

## 一次性安装（最简单）

从包：`source agent/setup.sh && bash agent/setup_af3.sh` — 创建 `af3` env，构建扩展，并放置打包的 CCD。权重已在 `af3_assets/`。手动等价步骤见下。

## 在工作站上一次性安装（手动）

```bash
cd agent/third_party/alphafold3
conda env create -f af3_env.yml            # 创建 env "af3"
conda activate af3
pip install --no-deps -e .                 # 构建 C++ 扩展（需要 CMake）
build_data                                 # 重新生成 constants/converters/ccd.pickle
# 放置受控权重：
mkdir -p alphafold_param && cp /path/to/af3.bin.zst alphafold_param/
```

## 让包装指向安装

包装读取这些环境变量（所示默认是 pc101 安装）：

| 变量 | 含义 | 默认 |
|---|---|---|
| `AF3_DIR` | 含 `run_alphafold.py` 的 AF3 仓目录 | `/workspace/shared/code/rna/alphafold3` |
| `AF3_PARAMS` | 存放 `af3.bin.zst` 的目录 | `$AF3_DIR/alphafold_param` |
| `AF3_PYTHON` | `af3` conda env 的 python | `/workspace/shared/envs/rna/af3/bin/python` |
| `AF3_CACHE` | JAX 编译缓存（可再生成） | `$AF3_DIR/alphafold_cache` |

在新机器上，将这些设为 vendored 副本，例如
`export AF3_DIR=$PWD/agent/third_party/alphafold3` 以及
`AF3_PYTHON=$(conda run -n af3 which python)`。

## 用法

```bash
# 1) 仅 MSA（缓存的 a3m 可复用；--seq/--out CLI，或 Python 中 get_msa()）
python colabfold_msa.py --seq MQIFVKTLTGK... --out ubq.a3m

# 2) 预测结构（自动获取 MSA）
python structure_predict_af3.py --json '{"sequence":"MQIFVKTLTGK...","name":"UBQ"}'
#   -> {"ok":true,"structure":".../UBQ_model.cif","mean_plddt":91.16,"ptm":0.84,
#       "ranking_score":0.84,"fraction_disordered":0.0,"has_clash":0.0,
#       "structured_core_plddt":96.35,"fraction_structured":0.961,
#       "per_residue_plddt":[...]}

# 2b) 结合区域置信度：传入 RBD 残基区间（1-indexed，闭区间）
python structure_predict_af3.py --json '{"sequence":"...","name":"PTBP1","regions":[[60,140],[180,260]]}'
#   -> 增加 "region_plddt": <那些残基上的 mean pLDDT> + 分区域分解

# 3) 为新 RBP 在 AFDB 与 AF3 之间择一
python structure_consensus.py --json '{"uniprot":"P0CG48","sequence":"MQIFVKTLTGK...","alias":"UBC"}'
#   -> {"chosen_structure":...,"tm_score":...,"afdb":{...},"af3":{...},"reason":...}
```

`structure_predict_af3` 以 `--norun_data_pipeline --run_inference` 调用 AF3
（MSA 已提供），因此唯一的网络调用是 ColabFold 的 MSA 服务器。

## 置信度指标（agent 读取的）

`structure_predict_af3` 与 `structure_consensus` 对每个模型暴露：

| 字段 | 含义 | 用途 |
|---|---|---|
| `mean_plddt` | 全原子 mean pLDDT（AF3 原生） | 整体折叠置信度 |
| `structured_core_plddt`、`fraction_structured` | 残基 ≥ `core_thresh`（默认 70）上的 mean pLDDT + 结构化比例 | 折叠核心的置信度，忽略无序尾（与结构域无关） |
| `region_plddt`、`regions[]` | 调用方提供的 RBD 区间上的 mean pLDDT | **与结合相关的** 置信度（从 `domain_architecture`/UniProt 传入 RBD 区间） |
| `per_residue_plddt[]` | 每残基（CA）pLDDT | 自定义聚合 / 作图 |
| `ptm`、`iptm`、`chain_ptm` | 预测 TM 分数 | 全局/界面拓扑置信度 |
| `ranking_score` | AF3 模型排序 | 模型选择 |
| `fraction_disordered`、`has_clash` | 全局 QC 标志 | 拒绝低质量模型 |
| `confidences_json` | AF3 完整 JSON 路径（PAE、contact_probs） | 高级用途 |

注意：`structured_core_plddt` ≥ `mean_plddt` 是正常的（全原子均值包含柔性侧链与无序残基）。

## 注意事项

- **必须清洗 MSA。** 原始 ColabFold a3m 可能含杂散字节，会弄崩 AF3 的 MSA 解析器（`Unknown residues in MSA`）；`colabfold_msa.py` 会净化 a3m（已验证：清洗后 MSA → ubiquitin pLDDT 91.16）。
- 每个序列长度的首次推断支付 JAX 编译（约数分钟）；缓存在 `AF3_CACHE`。
- AF3 **输出** 条款适用于预测结构 — 见 `OUTPUT_TERMS_OF_USE.md`。
- 在 pc101 上验证（1× RTX/A100 级 GPU，`af3` env，jax 0.4.34）。

---

## 9. tools/sequence/README.md

> 源文件：`tools/sequence/README.md`

# tools/sequence

序列相关工具（图：BLASTn / ESM）。契约见 [`../registry.json`](../registry.json)，理由见 [`../../DESIGN.md`](../../DESIGN.md) §3.B。

| 工具 | 状态 | 说明 |
|---|---|---|
| `protein_seq_similarity.py` | ✅ 已实现 | mmseqs 查询 vs `database/seq_db` → %id/e-value hits |
| `esm_embed.py` | ✅ 已实现 | 新序列 → 银行空间中的 ESM2/ESM-C/SaProt 均值向量；`--device cuda\|cpu` |
| `esm_similarity.py` | ✅ 已实现 | 嵌入 + 相对 `database/embedding_bank` 的 cosine → hits（ESM-C = 最佳迁移信号）；`--device cuda\|cpu` |
| `domain_architecture.py` | ✅ 已实现 | Pfam domains → RBD 感知重叠（家族根的 Jaccard）相似度 |
| `rna_blastn.py` | ✅ 已实现 | RNA 侧：查询 vs 406k POS 结合-peak DB（mmseqs nt）→ RBP hits |

**ESM 工具在 `protein_embed` env 中运行**（torch + transformers + esm）。SaProt 需要结构（`pdb_path`）+ foldseek + `SAPROT_REPO`。已验证：ESM-C/cuda 与 esm2/cpu 均复现 bank（PTBP1 自余弦 1.0）。

---

## 10. tools/function/README.md

> 源文件：`tools/function/README.md`

# tools/function

功能相关工具（图：Literature / UniProt / PDB ★）。★ = 为 LLM 产出干净结构化文本。契约见 [`../registry.json`](../registry.json)，理由见 [`../../DESIGN.md`](../../DESIGN.md) §3.C 与 §4。

| 工具 | 状态 | 说明 |
|---|---|---|
| `uniprot_annotation.py` ★ | ✅ 已实现 | registry + UniProt REST 回退 → function/GO/keywords/RBD 类型 |
| `go_pfam_lookup.py` | ✅ 已实现 | 从 registry 对参考 RBP 做离线查询 |
| `function_category.py` | ✅ 已实现 | RBP → splicing/stability/translation/processing/Others |
| `pdb_metadata.py` ★ | ✅ 已实现 | acc → RCSB 条目、蛋白–RNA 复合物标志、配体 |
| `literature_retrieval.py` ★ | ✅ 已实现 | 名称 → Europe PMC abstracts/snippets |

---

## 11. tools/integrate/README.md

> 源文件：`tools/integrate/README.md`

# tools/integrate

第 3 步整合与校准（源自 LOO）。这些把 donor 预测 + 相似度变成一个可打分、可解释的判定，并向 LLM 提供证据表。契约见 [`../registry.json`](../registry.json)，理由见 [`../../DESIGN.md`](../../DESIGN.md) §3.E 与 §4。

| 工具 | 状态 | 说明 |
|---|---|---|
| `similarity_weighted_vote.py` | ✅ 已实现 | {donor: prob} × {donor: sim}（× 先验）→ score + contributions（确定性基线） |
| `transfer_prior_lookup.py` | ✅ 已实现 | target↔donor → 来自 `database/transfer` 的经验可靠性（LOO 矩阵；10 个实测 targets） |
| `confidence_abstain.py` | ✅ 已实现 | OOD：最佳相似度 < 按 metric 的阈值 → 低置信标志 |
| `donor_quality_prior.py` | ✅ 已实现 | 来自 registry 的每 RBP head val-AUPRC → 对弱 donor 降权 |

**交给 LLM 的输出**（★2 触点）：一张紧凑证据表 — 每个 donor：按模态的相似度、预测 prob、transfer prior、donor quality — 外加确定性基线分数与弃权标志。

---
## 12. eval/README.md

> 源文件：`eval/README.md`

# eval — 自演进 val harness

让工具包能在 held-out 数据上增长与加权（图中的"基于 val 集结果自演进 …"）。Agent/协作方用它度量新工具或加权是否真正改善端到端的新 RBP 预测。

## 协议（广义 LOO）

这是我们的 leave-one-RBP-out 实验变成评估循环：

1. 把每个 held-out RBP 当作 **新的**：隐藏其自身 head。
2. 运行候选 agent 策略（检索 donors → 用 donors 的 heads 预测 → 整合），为该 RBP 的测试 RNA 产生预测。
3. 相对 **own-head 上限**（真实 head 本应达到的）以及相对单任务 / mean-foreign 基线打分。

参考数字已存在于 [`../database/transfer`](../database/transfer)
（`loo_summary.csv`、`loo_transfer_metrics.csv`）：每个 RBP 的 own-head AUPRC、best-foreign、mean-foreign。恢复接近 best-foreign 的策略表现良好；到 own-head 的差距是提升空间。

## 要构建什么

- `run_eval.py` — 给定策略（选择 + 整合配置）→ 每个 RBP 的恢复 AUPRC、相对上限的差距、弃权率；汇总报告。
- **工具价值消融：** 开关每个工具 / 相似度模态并度量 val 集上的 delta → 告诉协作方哪些工具该保留、丢弃或上调权重（自演进信号）。

## 起始 val 集

10 个 LOO RBP（cluster medoids：NSUN2、FXR2、HNRNPUL1、EEF2、PTBP1、CPSF6、DHX30、DDX51、DROSHA、RPS6）已有完整的 donor×target transfer 实测 — 把它们用作初始 val 集；通过对更多 RBP 运行 LOO driver 来扩展。

---

## 13. examples/README.md

> 源文件：`examples/README.md`

# 示例 — 端到端 agent 流水线（冒烟测试）

retrieve → predict → integrate 流水线的自包含运行，以便新部署可对照已知正确输出验证。

**场景：** 把 **PTBP1** 当作 *新* RBP（假装我们没有它的 head），检索相似的已知 RBP，并通过 donor heads 对其一条 RNA 打分 — 这正是 agent 所基于的迁移步骤。因为 PTBP1 *确实* 在 panel 中，其 own-head 答案（AUPRC **0.9311**）可作为真值。

## 文件
- `new_rbp_PTBP1.fasta` — PTBP1 蛋白序列（"新 RBP" 输入）。
- `sample_rna_pos.txt`、`sample_rna_neg.txt` — 来自 PTBP1 的 K562 测试集的一条阳性 / 一条阴性 128-nt RNA。
- `run_example.sh` — 运行下面五步。

## 运行
```bash
source agent/setup.sh && bash agent/setup_envs.sh   # 一次性
bash agent/examples/run_example.sh            # 加 'cpu' 可在无 GPU 时跑第 2 步
```
在我们的开发机上预测器 env 是 `evo2`；设置 `RHOBIND_ENV=evo2`（包的默认是 `rhobind`，由 `setup_envs.sh` 创建）。

## 期望输出（黄金）

**1. resolve_rbp** → `in_panel: true`，`head_index {K562: 73, HepG2: 52}`。

**2. esm_similarity**（ESM-C，排除自身）→ top donors：
| rank | donor | cosine |
|---|---|---|
| 1 | U2AF2 | 0.964 |
| 2 | QKI | 0.957 |
| 3 | ELAVL1 | 0.950 |
| 4 | MBNL2 | 0.948 |
| 5 | CELF1 | 0.946 |
全部是 RRM RNA 结合蛋白 — 合理的邻域。

**3. domain_architecture** → `query_domain_families: ["RRM"]`；命中 HNRNPC、HNRNPL、U2AF2、TIA1、NCBP2（Jaccard 1.0；HNRNPL 共享精确的 Pfam IDs PF22976/13893/11835）。

**4. rhobind_predict** 在阳性 RNA 上：
| head | prob |
|---|---|
| PTBP1（自身） | **0.966** |
| U2AF2 | 0.076 |
| MATR3 | 0.006 |
| QKI | 0.147 |
自身 head 自信地判定这条阳性 RNA。**单条 RNA 的 donor probs 很嘈杂** —
迁移是 *聚合* 效应：在完整测试集上，最佳外来 head 恢复 AUPRC ≈ **0.825**，相对 own-head 0.931（见 `database/transfer/loo_summary.csv`）。
因此 agent 应对 donors 排序并汇集它们，而不是在一条 RNA 上信任单个 donor。

**5. similarity_weighted_vote**（示意性输入）→ 聚合 `score ≈ 0.649`，带每个 donor 的贡献。

**真值检查（可选，完整测试集）：**
```bash
conda run -n "$RHOBIND_ENV" python "$RHOBIND_RELEASE/infer.py" \
  --checkpoint "$RHOBIND_RELEASE/checkpoints/rhobind_k562_mt_all118_cutoff08.ckpt" \
  --head_index "$RHOBIND_RELEASE/checkpoints/head_index_k562.json" \
  --rbp PTBP1 --fasta "$RHOBIND_RELEASE/test_data/k562/PTBP1/test.fasta"
# -> AUPRC 0.9311  （匹配 release/rhobind_release_v1/expected_metrics.csv）
```

若第 1–3 步匹配且 own-head AUPRC 复现 0.9311，则部署良好。

---

## 14. database/README.md

> 源文件：`database/README.md`

# 支柱 1 — RBP 知识库（已知 RBP）

一份冻结的、只读的参考，描述我们已训练 panel 中的每个 RBP
（K562 = 118 与 HepG2 = 85 两个队列上共 238 个唯一蛋白）。Agent **对着它搜索**；查询时从不修改它。

## 布局

| 子文件夹 | 内容 | 状态 |
|---|---|---|
| `registry/` | `rbp_registry.json` — 每个 RBP 的主索引（由这里其余一切构建）。`rbp_registry.schema.json` — 其 schema。`manifest.tsv` — 原始蛋白元数据（UniProt、organism、seq_len、AFDB/PDB 交叉引用）。 | schema + manifest 已暂存；**registry 待构建** |
| `annotations/` | `pfam_long.tsv`、`go_long.tsv`、`go_pfam.tsv`（每个 UniProt 的 Pfam domains + GO terms）、`rbp_category_assignment.tsv`（splicing / stability / translation / …）。 | **已暂存** |
| `similarity/` | 预计算的成对相似度矩阵（`sim_*.npz`，每个 = `{matrix, symbols, uniprots}`）：`seqid`（mmseqs %id）、`foldseek`（lDDT/TM/fident）、`esmc`、`esm2`、`saprot`（cosine）。 | **已暂存（118×118）；扩展到 238** |
| `transfer/` | `loo_transfer_metrics.csv`（donor→target transfer AUPRC，1170 对）、`loo_summary.csv`、`loo_rest_of_cohort.csv`。第 3 步先验与弃权的经验基础。 | **已暂存** |
| `clustering/` | `k562_cluster_assignment.csv` / `_summary.csv` — ESM-C 功能 clusters + 标签 + motifs。 | **已暂存** |
| `sequences/`、`structures/`、`embeddings/` | 重型参考数据 — 见 [`SOURCES.md`](SOURCES.md)。不复制到此处；在 `pc157` 上。 | **在远端** |

## 主索引：`rbp_registry.json`

每个可用 RBP 一条记录，合并以上全部，使 agent 有单一查找入口。关键是它携带 **每个 RBP 的 head 可靠性先验**（val/test AUPRC）— 相似但建模很差的 donor 必须降权。Schema 见 [`registry/rbp_registry.schema.json`](registry/rbp_registry.schema.json)；用 [`SOURCES.md`](SOURCES.md) 中描述的组装器构建。

## 为什么这些矩阵重要（来自 LOO 研究）

`similarity/` + `transfer/` 一起让 agent 在不必重新推导的情况下回答 *"对这个新 RBP，我该信任哪个已知 RBP 的 head，以及信任多少？"*：
ESM-C cosine 是最一致的迁移预测因子；序列一致度与结构 lDDT 更嘈杂；而 `transfer/` 记录了实测上限，使整合层可以校准而不是猜测。

---

## 15. database/SOURCES.md

> 源文件：`database/SOURCES.md`

# 数据库来源与构建命令

重型参考数据位于 **pc157** 的
`RB=/workspace/jmwang/rna/interaction/data/clip_huiyang/rbp_proteins_260417`。
本文件记录来源以及组装运行时数据库的命令（在 pc157 上运行，env `protein_embed`，除非另注）。

## 远端源清单

| 数据 | 远端路径 | 大小 | agent 是否需要 |
|---|---|---|---|
| UniProt 规范序列（238） | `$RB/sequences/all_rbps.fasta` | 164 KB | **是** — 序列库 + 新 RBP 回退输入 |
| AFDB 模型（238） | `$RB/structures/afdb/*.pdb` | 95 MB | **是** — foldseek DB |
| PDB 条目（197） | `$RB/structures/pdb/` | 21 GB | 可选 — 实验复合物 |
| ESM-C 600M 嵌入（238，每残基） | `$RB/embeddings/esmc_600m/*.pkl` | 668 MB | **仅均值池化**（约 3 MB bank） |
| ESM2 / SaProt 嵌入（238） | `$RB/embeddings/{esm2,saprot}/*.pkl` | 约 1.4 GB | **仅均值池化** |
| Pfam / GO / category | `$RB/annotations/`，`…/our_pipeline/struct_pred_benchmark/rbp_category_assignment.tsv` | 小 | **是**（已暂存） |
| 每个 RBP 的基准性能 | `…/rhobind_dev_claude/results/benchmark_cluster/benchmark_{auprc,auc}_bench_cutoff_08*.csv` | 小 | **是** — head 可靠性先验 |
| LOO transfer 矩阵 | `…/rhobind_dev_claude/results/loo/` | 小 | **是**（已暂存） |

## 构建运行时数据库（在 pc157 上）

```bash
DST=/workspace/jmwang/rna/interaction/agent_db     # 运行时 DB 根
mkdir -p $DST/{embedding_bank,foldseek_db,seq_db,registry}

# 1) 将每残基嵌入均值池化为紧凑 bank（每个编码器一个矩阵 + id 列表）
#    -> $DST/embedding_bank/{esmc,esm2,saprot}.npz  （每个 ≈3 MB）
python build_embedding_bank.py --src $RB/embeddings --out $DST/embedding_bank   # [待编写]

# 2) 从 238 个 AFDB 模型建 Foldseek 结构 DB
foldseek createdb $RB/structures/afdb $DST/foldseek_db/refs

# 3) 从 238 条 UniProt 序列建 mmseqs 序列 DB
mmseqs createdb $RB/sequences/all_rbps.fasta $DST/seq_db/refs

# 4) 组装主 registry（合并 manifest + 注释 + clusters +
#    功能类别 + 每个 RBP 的基准 AUPRC + 路径）-> rbp_registry.json
python build_registry.py --rb $RB --benchmarks .../results/benchmark_cluster \
    --out $DST/registry/rbp_registry.json                                      # [待编写]
```

`build_embedding_bank.py` 与 `build_registry.py` 是两个待编写的小型 Phase-0 脚本；foldseek/mmseqs DB 是一行命令。此处其余一切已产出 — 构建是索引 + 合并，不是重算。

---

## 状态：已构建（Phase 0 完成）

运行时 DB 根：`pc157:/workspace/jmwang/rna/interaction/agent_db/`

| 产物 | 路径 | 结果 |
|---|---|---|
| Embedding banks | `embedding_bank/{esmc,esm2,saprot}.npz` + `ids.json` | 238 × {1152,1280,1280} |
| Foldseek DB | `foldseek_db/refs*` | 238 模型；自命中 TM=1.0，RRM 邻居已验证 |
| mmseqs 序列 DB | `seq_db/refs*` | 238 序列；自命中置顶，同源已验证 |
| Registry | `registry/rbp_registry.json` | 238 条记录，140 有 heads；K562 平均 AUPRC 0.6848（n=118）匹配基准 |
| Backbone（持久） | `backbone/` | release 包 + 供 `rhobind_predict` 的精简 checkpoints |

构建脚本：`agent/database/build/build_{embedding_bank,registry}.py`。
小产物的本地镜像：`agent/database/{registry,embedding_bank,...}`。
包装已验证：`agent/tools/utility/resolve_rbp.py`、`agent/backbone/predict_api.py`。

> 检索工具注意：直接解析 foldseek/mmseqs 的数值输出列 —
> shell `sort -n` 会错误排序科学计数法（`1.0E+00` vs `8.8E-01`）。

---

## 16. backbone/README.md

> 源文件：`backbone/README.md`

# 支柱 3 — RhoBind 骨干（独立预测器）

已训练的相互作用预测器 — agent 的第 2 步。它 **已经是交付物**；本支柱把它包装为预测 API，并且 **不** 复制或修改它。

## 权威来源

独立骨干位于 [`../../release/`](../../release)：
`rhobind_release_v1/`（已解压）与 `rhobind_release_v1.tar.gz`。它包含模型代码（`rhobind/`）、两个已发布 checkpoints（K562 118-head、HepG2 85-head）、head-index 映射，以及 `infer.py`。两个 checkpoints 都精确复现已发布的每个 RBP AUPRC（已验证，含 clean-room）。

## Agent 如何使用它

对 **新** RBP，agent 在查询 RNA 上运行 **donor** RBP 的 heads — 这是经验验证过的迁移动作（LOO：当存在亲属时，最佳外来 head ≈ 自身 head）。暴露为 `rhobind_predict` 工具：

```
rhobind_predict(rna, rbps=[donor aliases], cohort) -> [{alias, prob, head_index, cohort}, ...]
```

### 要写的包装（薄）

`predict_api.py` — 从 release 包 import `rhobind.load_rhobind`，把模型保持在内存中，并对一条 RNA 批量给一组 donor aliases 打分（在 `rna_preprocess` 切窗之后）。在 `release/rhobind_release_v1/infer.py` 之上约 30 行；
无重训，无新权重。

> 不要把 checkpoints 复制到这里 — 引用 release 包，使已发布模型只有单一权威来源。

---
## 17. tools/registry.json — 工具清单全文对照

> 源文件：`tools/registry.json`

以下为 registry 的中文对照译本。字段名（`name`、`input_schema` 键等）保持英文，因其为机器契约；`description` / `summary` 译为中文。

- **schema_version：** `1.0`
- **description（中文）：** Agent 读取以发现能力的工具清单。status: ready=已实现并验证（可运行 <category>/<name>.py）| build=计划中。在此添加工具 + adapter 以扩展工具包（自演进）。
- **description（原文）：** Tool manifest the agent reads to discover capabilities. status: ready=implemented & validated (runnable <category>/<name>.py) | build=planned. Add a tool here + an adapter to extend the toolkit (self-evolving).

### shared_types

```json
{
  "RbpHit": {
    "alias": "str",
    "uniprot": "str",
    "score": "float",
    "metric": "str",
    "rank": "int"
  },
  "Prediction": {
    "alias": "str",
    "prob": "float",
    "head_index": "int",
    "cohort": "str"
  }
}
```

### tools（共 24 个）

#### `structure_fetch`

- **category：** `structure`
- **status：** `ready`
- **network：** `True`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** UniProt accession → AFDB 模型（先本地 DB，否则下载）。
- **summary（原文）：** UniProt acc -> AFDB model (local DB first, else download).
- **input_schema：** `{"uniprot": "str"}`
- **output_schema：** `{"pdb_path": "str", "source": "str"}`

#### `structure_predict_af3`

- **category：** `structure`
- **status：** `ready`
- **network：** `True`
- **gpu：** `True`
- **est_runtime：** `min`
- **summary（中文）：** 蛋白序列 → 本地 AlphaFold3 结构 + 置信度。ColabFold MMseqs2 API 提供 MSA（在线）；AF3 以 --norun_data_pipeline 在本地运行。权重内部打包（af3_assets/；setup.sh 设置 AF3_PARAMS）。可选 `regions`（RBD 区间）→ 结合区域 pLDDT。见 third_party/alphafold3 + AF3_SETUP.md。
- **summary（原文）：** Protein sequence -> local AlphaFold3 structure + confidence. ColabFold MMseqs2 API supplies the MSA (online); AF3 runs locally with --norun_data_pipeline. Weights bundled internally (af3_assets/; setup.sh sets AF3_PARAMS). Optional `regions` (RBD ranges) -> binding-region pLDDT. See third_party/alphafold3 + AF3_SETUP.md.
- **input_schema：** `{"sequence": "str", "name": "str", "regions": "[[int,int]]", "core_thresh": "float"}`
- **output_schema：** `{"ok": "bool", "structure": "str", "mean_plddt": "float", "ptm": "float", "iptm": "float", "chain_ptm": "float", "ranking_score": "float", "fraction_disordered": "float", "has_clash": "float", "structured_core_plddt": "float", "fraction_structured": "float", "region_plddt": "float", "regions": "object[]", "per_residue_plddt": "object[]", "confidences_json": "str"}`

#### `colabfold_msa`

- **category：** `structure`
- **status：** `ready`
- **network：** `True`
- **gpu：** `False`
- **est_runtime：** `min`
- **summary（中文）：** 蛋白序列 → 经 ColabFold MMseqs2 API 的 MSA（a3m）。为 AF3 解析器清洗。由 structure_predict_af3 使用；缓存 a3m 以便复用。
- **summary（原文）：** Protein sequence -> MSA (a3m) via the ColabFold MMseqs2 API. Cleaned for AF3's parser. Used by structure_predict_af3; cache a3m to reuse.
- **input_schema：** `{"sequence": "str"}`
- **output_schema：** `{"a3m": "str", "n_seqs": "int"}`

#### `structure_consensus`

- **category：** `structure`
- **status：** `ready`
- **network：** `True`
- **gpu：** `True`
- **est_runtime：** `min`
- **summary（中文）：** 从 AFDB + 本地 AF3 为新 RBP 选择结构：TM-score 一致性（foldseek）+ CA-pLDDT/pTM 置信度 → 选定结构 + low_agreement 标志。当一者/两者缺失时优雅回退。
- **summary（原文）：** Pick a new RBP's structure from AFDB + local AF3: TM-score agreement (foldseek) + CA-pLDDT/pTM confidence -> chosen structure + low_agreement flag. Falls back gracefully when one/both are absent.
- **input_schema：** `{"uniprot": "str", "sequence": "str", "alias": "str", "agree_tm": "float"}`
- **output_schema：** `{"chosen_structure": "str", "tm_score": "float", "afdb": "object", "af3": "object", "reason": "str"}`

#### `struct_similarity_foldseek`

- **category：** `structure`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** 查询结构 vs 参考 foldseek DB → 排序的 RbpHit（lDDT/TM）。
- **summary（原文）：** Query structure vs reference foldseek DB -> ranked RbpHit (lDDT/TM).
- **input_schema：** `{"pdb_path": "str", "top_k": "int"}`
- **output_schema：** `{"hits": "RbpHit[]"}`

#### `struct_align_usalign`

- **category：** `structure`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** 查询 vs 目标 RBP 的精确 TM-score（US-align；foldseek TM-align 回退）（aliases→AFDB 或 pdb 路径）。精修 foldseek hits。需要 USalign 二进制（环境变量 USALIGN / agent_db/bin/USalign）。
- **summary（原文）：** Precise TM-score (US-align; foldseek TM-align fallback) for query vs target RBPs (aliases->AFDB or pdb paths). Refines foldseek hits. Needs USalign binary (env USALIGN / agent_db/bin/USalign).
- **input_schema：** `{"query_pdb": "str", "targets": "str[]"}`
- **output_schema：** `{"hits": "RbpHit[]", "method": "str"}`

#### `pymol_util`

- **category：** `structure`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** 从结构取序列、清洗、可选渲染。
- **summary（原文）：** Sequence-from-structure, cleaning, optional render.
- **input_schema：** `{"pdb_path": "str", "op": "str"}`
- **output_schema：** `{"result": "object"}`

#### `protein_seq_similarity`

- **category：** `sequence`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** 新 RBP 序列 vs 参考序列库（mmseqs）→ 排序的 RbpHit（%id、e-value）。
- **summary（原文）：** New RBP sequence vs reference seq DB (mmseqs) -> ranked RbpHit (%id, e-value).
- **input_schema：** `{"sequence": "str", "top_k": "int"}`
- **output_schema：** `{"hits": "RbpHit[]"}`

#### `esm_embed`

- **category：** `sequence`
- **status：** `ready`
- **network：** `False`
- **gpu：** `True`
- **est_runtime：** `s`
- **summary（中文）：** 在 bank 空间中嵌入新序列（ESM2/ESM-C/SaProt；saprot 需要 pdb_path）。--device cuda|cpu。在 protein_embed env 中运行。
- **summary（原文）：** Embed a new sequence in the bank's space (ESM2/ESM-C/SaProt; saprot needs pdb_path). --device cuda|cpu. Run in protein_embed env.
- **input_schema：** `{"sequence": "str", "encoder": "str", "device": "str", "pdb_path": "str"}`
- **output_schema：** `{"ok": "bool", "vector": "float[]", "dim": "int", "encoder": "str", "device": "str"}`

#### `esm_similarity`

- **category：** `sequence`
- **status：** `ready`
- **network：** `False`
- **gpu：** `True`
- **est_runtime：** `s`
- **summary（中文）：** 对查询做 esm_embed，再相对嵌入库做 cosine → 排序的 RbpHit。ESM-C 是最可靠的迁移预测因子（LOO）。--device cuda|cpu。
- **summary（原文）：** esm_embed the query then cosine vs the embedding bank -> ranked RbpHit. ESM-C is the most reliable transfer predictor (LOO). --device cuda|cpu.
- **input_schema：** `{"sequence": "str", "encoder": "str", "top_k": "int", "device": "str", "uniprot": "str"}`
- **output_schema：** `{"ok": "bool", "hits": "RbpHit[]"}`

#### `domain_architecture`

- **category：** `sequence`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** 查询 Pfam domains（payload/registry/InterProScan）→ 相对 refs 的 RBD 感知重叠（Pfam 家族根的 Jaccard）→ 排序的 RbpHit。结合由结构域驱动（RRM/KH/zf）。
- **summary（原文）：** Query Pfam domains (payload/registry/InterProScan) -> RBD-aware overlap (Jaccard of Pfam family roots) vs refs -> ranked RbpHit. Binding is domain-driven (RRM/KH/zf).
- **input_schema：** `{"sequence": "str", "alias": "str", "uniprot": "str", "domains": "object[]", "top_k": "int", "network": "bool"}`
- **output_schema：** `{"ok": "bool", "query_domain_families": "str[]", "hits": "RbpHit[]"}`

#### `rna_blastn`

- **category：** `sequence`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** RNA 侧：查询 RNA vs POS 结合-peak 核苷酸库（mmseqs --search-type 3）→ 其已知位点与之相似的 RBP。DB：build_peaks_db.py（环境变量 PEAKS_DB）。在 rna env 中运行。
- **summary（原文）：** RNA-side: query RNA vs the POS binding-peak nucleotide DB (mmseqs --search-type 3) -> RBPs whose known sites it resembles. DB: build_peaks_db.py (env PEAKS_DB). Run in rna env.
- **input_schema：** `{"rna": "str", "top_k": "int"}`
- **output_schema：** `{"hits": "object[]", "total_peak_matches": "int"}`

#### `uniprot_annotation`

- **category：** `function`
- **status：** `ready`
- **llm_facing：** `True`
- **network：** `True`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** accession → 结构化功能 JSON（功能文本、GO、keywords、domains、RBD 类型）。
- **summary（原文）：** acc -> structured function JSON (function text, GO, keywords, domains, RBD type).
- **input_schema：** `{"uniprot": "str"}`
- **output_schema：** `{"annotation": "object"}`

#### `pdb_metadata`

- **category：** `function`
- **status：** `ready`
- **llm_facing：** `True`
- **network：** `True`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** accession/结构 → PDB 条目、蛋白-RNA 复合物、结合配体。
- **summary（原文）：** acc/structure -> PDB entries, protein-RNA complexes, bound ligands.
- **input_schema：** `{"uniprot": "str"}`
- **output_schema：** `{"entries": "object[]"}`

#### `literature_retrieval`

- **category：** `function`
- **status：** `ready`
- **llm_facing：** `True`
- **network：** `True`
- **gpu：** `False`
- **est_runtime：** `s`
- **summary（中文）：** RBP 名称 → PubMed/Europe PMC abstracts/snippets，供功能推理。
- **summary（原文）：** RBP name -> PubMed/Europe PMC abstracts/snippets for function reasoning.
- **input_schema：** `{"name": "str", "max_results": "int"}`
- **output_schema：** `{"papers": "object[]"}`

#### `go_pfam_lookup`

- **category：** `function`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** 从数据库对参考 RBP 做离线注释查询。
- **summary（原文）：** Offline annotation lookup for reference RBPs from the database.
- **input_schema：** `{"uniprot": "str"}`
- **output_schema：** `{"pfam": "object[]", "go": "object"}`

#### `function_category`

- **category：** `function`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** RBP → splicing/stability/translation/processing/other。
- **summary（原文）：** RBP -> splicing/stability/translation/processing/other.
- **input_schema：** `{"uniprot": "str"}`
- **output_schema：** `{"category": "str"}`

#### `rhobind_predict`

- **category：** `backbone`
- **status：** `ready`
- **network：** `False`
- **gpu：** `True`
- **est_runtime：** `s`
- **summary（中文）：** （RNA 序列/FASTA、donor RBP aliases、cohort）→ 使用该 RBP 的 head 给出每个 RBP 的 Prediction。包装独立骨干。
- **summary（原文）：** (RNA seq/FASTA, donor RBP aliases, cohort) -> per-RBP Prediction using that RBP's head. Wraps the standalone backbone.
- **input_schema：** `{"rna": "str", "rbps": "str[]", "cohort": "str"}`
- **output_schema：** `{"predictions": "Prediction[]"}`

#### `rna_preprocess`

- **category：** `backbone`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** 任意 RNA → 128-nt 窗口（U→T，按 window/stride 切分）供 rhobind_predict；agent 聚合每窗口 probs（max/mean）。
- **summary（原文）：** Arbitrary RNA -> 128-nt windows (U->T, tiling by window/stride) for rhobind_predict; agent aggregates per-window probs (max/mean).
- **input_schema：** `{"rna": "str", "window": "int", "stride": "int"}`
- **output_schema：** `{"windows": "object[]", "n_windows": "int"}`

#### `similarity_weighted_vote`

- **category：** `integrate`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** {donor: prob} × {donor: similarity} → 聚合分数 + 每个 donor 的贡献。LLM 解释的确定性基线。
- **summary（原文）：** {donor: prob} x {donor: similarity} -> aggregate score + per-donor contributions. Deterministic baseline the LLM explains.
- **input_schema：** `{"predictions": "Prediction[]", "hits": "RbpHit[]"}`
- **output_schema：** `{"score": "float", "contributions": "object[]"}`

#### `transfer_prior_lookup`

- **category：** `integrate`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** target↔donor → 来自 LOO 矩阵的经验迁移可靠性；对迁移差的 donor 降权。
- **summary（原文）：** target<->donor -> empirical transfer reliability from the LOO matrix; down-weight poorly-transferring donors.
- **input_schema：** `{"target": "str", "donors": "str[]"}`
- **output_schema：** `{"priors": "object[]"}`

#### `confidence_abstain`

- **category：** `integrate`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** OOD 检查：若最大相似度 < 由 LOO 导出的阈值 → 低置信/弃权标志。
- **summary（原文）：** OOD check: if max similarity < LOO-derived threshold -> low-confidence/abstain flag.
- **input_schema：** `{"hits": "RbpHit[]"}`
- **output_schema：** `{"confident": "bool", "max_similarity": "float"}`

#### `donor_quality_prior`

- **category：** `integrate`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** 来自 registry 的每个 RBP head 可靠性（val AUPRC）；对相似但建模很差的 donor 降权。
- **summary（原文）：** Per-RBP head reliability (val AUPRC) from the registry; discount similar-but-badly-modeled donors.
- **input_schema：** `{"donors": "str[]", "cohort": "str"}`
- **output_schema：** `{"quality": "object[]"}`

#### `resolve_rbp`

- **category：** `utility`
- **status：** `ready`
- **network：** `False`
- **gpu：** `False`
- **est_runtime：** `ms`
- **summary（中文）：** 自由文本名称 / 同义词 / accession → 规范 {alias, uniprot}。使用 manifest gene_synonyms；处理杂乱输入与 isoform 怪癖（NIPBL iso2、RBM10 多 id）。
- **summary（原文）：** Free-text name / synonym / accession -> canonical {alias, uniprot}. Uses manifest gene_synonyms; handles the messy-input + isoform quirks (NIPBL iso2, RBM10 multi-id).
- **input_schema：** `{"query": "str"}`
- **output_schema：** `{"alias": "str", "uniprot": "str", "in_panel": "bool"}`


---

*译本完。原文路径见各节「源文件」标注。*
