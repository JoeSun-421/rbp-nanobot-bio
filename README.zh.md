<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="420">

  <h1>nanobot-bio</h1>
  <p>RNA–RBP 相互作用预测 Agent</p>

  <p>
    <a href="https://github.com/JoeSun-421/rbp-nanobot-bio/stargazers"><img src="https://img.shields.io/github/stars/JoeSun-421/rbp-nanobot-bio?style=flat" alt="Stars"></a>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python ≥3.10">
    <img src="https://img.shields.io/badge/version-0.5.1-green" alt="Version">
    <a href="https://github.com/JoeSun-421/rbp-nanobot-bio/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/JoeSun-421/rbp-nanobot-bio/ci.yml?branch=main&label=CI" alt="CI"></a>
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p><a href="README.md">English</a> · <b>中文</b></p>
</div>

## 这是什么

nanobot-bio 是一个命令行 Agent，用来估计一段 RNA 与某个 RBP（RNA-binding protein）是否可能结合，以及结合强弱大致如何。

本仓库提供 **Agent 层**（CLI、工具编排、对话与 verdict 格式）。真正的数值预测、RBP 注册表、embedding / 结构索引、RhoBind checkpoint 等，都在同级科学工具包 **`rhobind_agent_delivery`** 里。Agent 通过只读 bridge 调用它们；LLM 负责选工具、走完阶段约束、写解释，**不编造** `p_hat`。

调用链：

```text
用户提问
  → nanobot-bio CLI（agent / chat）
  → 仓内 Nanobot runtime + RBP toolkit
  → 只读 science bridge
  → rhobind_agent_delivery（打分与检索）
  → JSON verdict
```

适合本地装好 delivery 后做交互式查询、协作方装机验收，以及在固定问题上回归 own-head / LLM touchpoint。

### Verdict 字段

| 字段 | 含义 |
|------|------|
| `label` | 结合标签（如 Strong / Likely / Unlikely），由 `p_hat` 与阈值切分 |
| `confidence` | 本次运行对结论的把握（证据不足时可能偏低或弃权） |
| `p_hat` | 结合概率估计，只来自 predict 工具 |
| `explanation` | 文字说明（可由 LLM 在工具结果上整理） |
| `supporting_rbps` | 支撑结论的 RBP / donor |

默认标签阈值（`config/defaults.yaml`，可改）：

| 条件 | 标签倾向 |
|------|----------|
| `p_hat ≥ 0.75` | Strong |
| `p_hat ≥ 0.50` | Likely |
| `p_hat ≥ 0.25` | Unlikely |
| 更低 | 更偏向不结合一侧（以配置与归一化逻辑为准） |

示例：

```json
{
  "label": "Strong",
  "confidence": "high",
  "p_hat": 0.966,
  "explanation": "...",
  "supporting_rbps": ["PTBP1"]
}
```

## 环境要求

| 项 | 说明 |
|----|------|
| OS | 推荐 Linux x86_64；Ubuntu 20.04+ 验证过。macOS / WSL 可跑 agent 层，科学栈未完整验证 |
| Python | ≥ 3.10，推荐 3.13 |
| 磁盘 | 完整科学栈建议预留 ≥ 30 GB（delivery 与 conda 环境合计） |
| GPU | 可选；predict / ESM / AF3 等会受益。无 GPU 仍可跑 `doctor` 与轻量对话 |
| Delivery | `rhobind_agent_delivery` 与本仓库同级（同一父目录） |
| LLM | OpenAI 兼容 API key；`onboard` 写入本机配置 |

Delivery 需单独获取（协作方拷贝，或按 delivery 文档从零构建）。细节见 [INSTALL.md](INSTALL.md)。

## 安装

```bash
# 父目录下应同时有：
#   rbp-nanobot-bio/          （本仓库）
#   rhobind_agent_delivery/   （科学工具包）

git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

bash scripts/setup_all.sh              # agent venv + conda 科学环境
# bash scripts/setup_all.sh --skip-conda   # 只要 agent 层

source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
```

注意：

- 不要 `pip install nanobot-ai`，会抢 `import nanobot`，与仓内精简版冲突。
- `setup_all.sh` 使用仓内 `nanobot/`，不再依赖兄弟目录里另装一份 Nanobot。
- Docker：`docker compose build`（agent-only）或 `docker compose --profile full build`（完整科学栈）。见 [INSTALL.md](INSTALL.md)。

## 使用

### 日常命令

| 命令 | 说明 |
|------|------|
| `nanobot-bio onboard` | 配置 LLM 厂商、API key、模型 |
| `nanobot-bio doctor` | 检查路径、registry、工具轴、就绪状态 |
| `nanobot-bio agent --message "..."` | 一次性提问 → verdict |
| `nanobot-bio chat` | 多轮对话 |

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: AUCG..."
nanobot-bio chat
```

对话斜杠命令：`/help` · `/status` · `/tools` · `/new` · `/quit`。

提问尽量写清：

1. **RBP 名称**（如 PTBP1）
2. **RNA 序列**，或说明序列来自哪个文件 / 粘贴内容
3. 若有上下文（细胞系、只关心 panel 内等），可一并写上

Agent 会先 `resolve_rbp`，再按是否在 panel 内分支。

### 提问示例

```text
Does this RNA interact with RBP PTBP1?
RNA: GGUCU...（完整序列）

这段 RNA 会和 PTBP1 结合吗？序列如下：...

Query RBP is not in the usual panel. RNA: ... ; protein sequence / UniProt: ...
```

多轮里可以追问「为什么是 Likely」「supporting_rbps 是谁」「如果换另一条 RNA 呢」——新问题仍应带上序列，避免指代不清。

### 路由逻辑

**Panel 内（有 own head）**

1. `resolve_rbp` → `in_panel=true`
2. 调用一次 `predict_interaction`（own head）
3. 将 `predictions[0].prob` 映射为 `p_hat` / `label`
4. 输出 JSON verdict 并停止  
   此路径不跑 transfer、序列相似度检索、domain / literature 等扩展工具。

**未见靶标（无 own head）**

1. 多轴检索相似 **donor**（embedding、sequence、domain、structure 等，由 `config/defaults.yaml` 的 `axes` 控制）
2. 在 donor 预测头上 `predict_interaction`
3. 按相似度与弃权规则融合（`integrate` / `abstain_thresholds`）
4. 输出一次 verdict；`p_hat` 仍只来自 predict 工具

已知自检：delivery 示例阳性 RNA × **PTBP1** → own-head ≈ **0.966**。

### 验收与工程命令（可选）

协作方或发版前常用：

| 命令 | 说明 |
|------|------|
| `nanobot-bio accept-golden` | own-head golden（无 LLM；PTBP1 × 阳性 RNA） |
| `nanobot-bio accept-llm` | LLM touchpoint 验收（需 API key） |
| `nanobot-bio gap-closure` | Stage-0 / unseen 等证据报告 |
| `nanobot-bio gate` | ruff + pytest + layout 等工程门 |

报告默认写到 `artifacts/reports/`。公开 CI 只跑轻量 `test` job；带 delivery / GPU 的 science job 需 self-hosted runner，见 [INSTALL.md](INSTALL.md) 与 [RELEASE.md](RELEASE.md)。

本地测试：

```bash
python -m pytest -q
```

## 配置

主配置：`config/defaults.yaml`。

| 配置块 | 作用 |
|--------|------|
| `top_k` / `n_cand` | 检索与候选数量 |
| `axes.*` | 是否启用 embedding、sequence、domain、structure、AF3、literature 等 |
| `fusion_weights` | 多信号融合权重 |
| `label_thresholds` | `p_hat` → label |
| `abstain_thresholds` | 相似度过低时弃权 |
| `integrate` | transfer prior、donor 质量、是否启用 abstain |
| `llm.*` | 是否启用 LLM touchpoint（功能推理 / 最终解释） |

LLM 凭证：`nanobot-bio onboard` → 通常 `~/.nanobot/config.json`（建议 `chmod 600`）。可用 `NANOBOT_CONFIG` 改路径。**不要提交密钥。**

| 环境变量 | 用途 |
|----------|------|
| `BIO_ROOT` | 本仓库与 delivery 的共同父目录 |
| `DELIVERY_ROOT` | `rhobind_agent_delivery` 根路径 |
| `NANOBOT_BIO_ROOT` | 本仓库根目录 |
| `NANOBOT_WORKSPACE` | Agent 工作区（默认 `workspace/`） |
| `NANOBOT_CONFIG` | LLM 配置文件 |
| `RHOBIND_DEVICE` | `auto` / `cuda` / `cpu` |
| `AGENT_DB` | registry、embedding、各类 DB 根目录 |

完整变量表与 Docker volume 见 [INSTALL.md](INSTALL.md)。阶段门禁见 [AGENTS.md](AGENTS.md) 与 `workspace/AGENTS.md`。

## 局限与注意

- 无 delivery 时只能装起 agent 壳；真实打分不可用。
- 预测依赖 panel / donor 覆盖与模型质量，**不是**湿实验替代品。
- AF3 在无 AFDB 时可能 deferred 或失败；失败会记 caveat，其它轴仍可继续（见 INSTALL 常见问题）。
- `docs/` 若存在，默认本地保留、不随公开仓库推送。

## 相关文档

| 文档 | 内容 |
|------|------|
| [INSTALL.md](INSTALL.md) | 安装路径、环境变量、Docker、验收 |
| [AGENTS.md](AGENTS.md) | Agent 阶段约束 |
| [RELEASE.md](RELEASE.md) | 发版与 CI runner |
| [VENDOR.md](VENDOR.md) | 仓内 Nanobot 精简说明 |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |

## License

MIT。

## 致谢

- Agent runtime 基于 [HKUDS/nanobot](https://github.com/HKUDS/nanobot)
- 科学预测与数据来自 `rhobind_agent_delivery`
- 维护者：[JoeSun-421](https://github.com/JoeSun-421)
