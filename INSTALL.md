# 安装指南（协作方入门）

> 本文件是面向**新协作方**的单一入门。涵盖三条安装路径、完整环境变量表、数据获取与验收流程。
> 仓库 README 是产品概览；本文件聚焦"如何把它跑起来"。

**English** | [中文](INSTALL.zh.md)（本文件即中文版，英文版待补）

---

## 0. 前置条件

| 项 | 要求 | 说明 |
|----|------|------|
| OS | Linux x86_64（Ubuntu 20.04+ 验证通过） | macOS/WSL 可跑 agent 层，科学栈未验证 |
| 磁盘 | ≥ 30 GB 空闲 | delivery bundle ~15 GB；conda 科学栈 ~10 GB |
| Python | ≥ 3.10（agent 层）；nanobot 运行时需 ≥ 3.13 | 见路径说明 |
| conda / mamba | full 路径必需；agent 路径可选 | 推荐 mamba 加速 |
| GPU | 可选 | rhobind_predict / ESM / AF3 受益；CPU 可跑 doctor + chat |
| LLM API key | `agent` / `chat` / `accept-llm` 必需 | 通过 `nanobot-bio onboard` 配置 |

---

## 1. 三条安装路径

### 路径 A：一键脚本（最快，推荐首次使用）

```bash
git clone <this-repo> nanobot-bio
# delivery bundle 需单独获取（见 §3），放到同级目录：
#   bio_agent/
#     ├── nanobot-bio/
#     └── rhobind_agent_delivery/
cd nanobot-bio
bash scripts/setup_all.sh           # full 科学栈 + agent venv
# 或仅 agent 层（无 conda）：
# bash scripts/setup_all.sh --skip-conda

source .venv/bin/activate
nanobot-bio onboard                  # 配置 LLM provider + key
nanobot-bio doctor                   # 自检
```

`setup_all.sh` 会自动 clone 上游 nanobot 运行时到 `$BIO_ROOT/nanobot`（可用 `NANOBOT_NO_CLONE=1` 禁止）。

### 路径 B：Docker（隔离环境，推荐给只跑不开发的协作方）

```bash
cd nanobot-bio
# agent-only 镜像（轻）
docker compose build
# 或 full 科学栈镜像（重，需 GPU）
docker compose --profile full build

# 把 LLM 配置挂进去（首次需先在宿主机 onboard，或直接挂 config）
docker compose run --rm app onboard

# 自检 + 交互式 chat
docker compose run --rm app doctor
docker compose up app                # = nanobot-bio chat
```

数据 bundle 通过 volume 挂载（见 `docker-compose.yml`），不烤进镜像。详见 [Dockerfile](Dockerfile) 头部注释。

### 路径 C：手动 venv + conda（精细控制）

```bash
# 1. delivery 科学栈 conda envs
cd rhobind_agent_delivery
bash agent/setup_envs.sh             # protein_embed / rna / rhobind / af3

# 2. nanobot 运行时（需 Python ≥ 3.13）
git clone --depth 1 https://github.com/HKUDS/nanobot.git ../nanobot

# 3. agent venv
cd ../nanobot-bio
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install -e ".[dev]"

# 4. 让 venv 看见 sibling nanobot（写 .pth）
SITE=$(python -c 'import site; print(site.getsitepackages()[0])')
echo "$(cd .. && pwd)" > "$SITE/_nanobot_src.pth"

# 5. 同步插件 overlay + 写 .env
python -m app.sync_overlay
cp .env.example .env                # 按需编辑
nanobot-bio doctor
```

---

## 2. 环境变量总表

合并自 [README §6](README.md)、[`.env.example`](.env.example)、[`app/backends/delivery/env.py`](app/backends/delivery/env.py)、delivery `setup.sh`。`apply_delivery_env()` 会为缺失项填默认值，所以**只有覆盖默认时才需手动设**。

| 变量 | 默认 | 必填 | 用途 |
|------|------|------|------|
| `BIO_ROOT` | `nanobot-bio/..` | 否 | 仓库父目录 |
| `DELIVERY_ROOT` | `$BIO_ROOT/rhobind_agent_delivery` | 是* | delivery 包根 |
| `NANOBOT_SRC` | `$BIO_ROOT/nanobot` | 是* | nanobot 运行时 |
| `NANOBOT_BIO_ROOT` | `nanobot-bio/` | 否 | app 包根 |
| `NANOBOT_WORKSPACE` | `$NANOBOT_BIO_ROOT/workspace` | 否 | nanobot 工作区 |
| `NANOBOT_CONFIG` | `~/.nanobot/config.json` | 是** | LLM 配置（含 key） |
| `AGENT_DB` | `$DELIVERY_ROOT/agent_db` | 否 | registry / embeddings / DBs |
| `RBP_REGISTRY` | `$AGENT_DB/registry/rbp_registry.json` | 否 | 238 条 RBP 注册表 |
| `RHOBIND_RELEASE` | `$DELIVERY_ROOT/release/rhobind_release_v1` | 否 | 预测器 checkpoint |
| `RBP_PROTEINS` | `$DELIVERY_ROOT/reference` | 否 | 参考蛋白/结构 |
| `AFDB_DIR` | `$RBP_PROTEINS/structures/afdb` | 否 | AFDB PDB 目录 |
| `TRANSFER_DIR` | `$AGENT_DB/transfer` | 否 | LOO transfer CSV |
| `EMB_BANK` | `$AGENT_DB/embedding_bank` | 否 | ESM embedding 库 |
| `FOLDSEEK_DB` | `$AGENT_DB/foldseek_db/refs` | 否 | foldseek 索引 |
| `SEQ_DB` | `$AGENT_DB/seq_db/refs` | 否 | mmseqs 序列索引 |
| `PEAKS_DB` | `$AGENT_DB/peaks_db/peaks` | 否 | peaks 索引 |
| `USALIGN` | `$AGENT_DB/bin/USalign` | 否 | 结构对齐二进制 |
| `AF3_DIR` | `$DELIVERY_ROOT/agent/third_party/alphafold3` | 否 | AF3 源码 |
| `AF3_PARAMS` | `$DELIVERY_ROOT/af3_assets/alphafold_param` | 否 | AF3 权重 |
| `AF3_PYTHON` | conda `af3` env python | 否 | AF3 解释器 |
| `RHOBIND_DEVICE` | `auto` | 否 | `auto`/`cuda`/`cpu` |
| `RBP_BACKEND` | `delivery` | 否 | 工具后端 |
| `HF_ENDPOINT` | `https://hf-mirror.com` | 否 | HF 镜像（ESM 权重） |
| `OMP_NUM_THREADS` | `4` | 否 | 科学工具线程数 |

\* `setup_all.sh` / Docker 会自动设；手动路径需自己 export。
\** `onboard` 会写入；agent/chat 命令读取。

---

## 3. 数据获取

delivery bundle（`rhobind_agent_delivery/`）含全部数据：238 条 registry、embedding 库、foldseek/mmseqs 索引、AFDB 结构、LOO transfer 矩阵、rhobind checkpoint、AF3 权重。

**两条获取路径：**

- **已有 bundle**（推荐）：从协作方处获取 `rhobind_agent_delivery/` 目录，放到 `$BIO_ROOT/` 下与 `nanobot-bio/` 同级。
- **从零重建**：见 [`rhobind_agent_delivery/agent/database/SOURCES.md`](../rhobind_agent_delivery/agent/database/SOURCES.md)（记录了 pc157 构建过程：`build_registry.py` / `build_embedding_bank.py` / foldseek / mmseqs）。重建脚本见 [`scripts/bootstrap_data.sh`](scripts/bootstrap_data.sh)（幂等）。

数据路径全部由上表环境变量驱动，bundle 放哪都行，只要 `DELIVERY_ROOT` / `AGENT_DB` 指对。

---

## 4. 验收流程

**权威验收路径：`nanobot-bio accept-golden`**（覆盖 delivery 原生 smoke 的断言）。

```bash
nanobot-bio doctor           # 1. 环境自检（路径/registry/skill/axes/AF3）
nanobot-bio accept-golden    # 2. own-head golden（PTBP1 × pos RNA ≈ 0.966）
nanobot-bio accept-llm       # 3. LLM touchpoint（需 API key）
nanobot-bio gap-closure      # 4. Stage-0 / unseen fixture 证据包
nanobot-bio gate             # 5. 工程门（ruff + pytest + layout + 可选 LOO）
```

delivery 原生 `agent/examples/run_example.sh` 仅用于**无 app 层时的回归**（直接调 delivery 脚本），协作方验收请走 `nanobot-bio accept-golden`。

报告输出到 `artifacts/reports/`（或 `~/.nanobot-bio/artifacts/reports/` 当 env 覆盖时）。

### 4.1 CI 与 self-hosted runner

`.github/workflows/ci.yml` 有三个 job：

| job | runner | 触发 | 作用 |
| --- | --- | --- | --- |
| `test` | `ubuntu-latest` | 每次 push/PR | ruff + pytest + layout + secret scan（公开 CI，无需 GPU） |
| `science` | `self-hosted, linux, science` | 仅 tag / 手动 | `accept-golden`（需 delivery bundle + 内存/GPU） |
| `eval` | `self-hosted, linux, science` | 仅 tag / 手动 | Stage-3 消融 + ECE（B5） |

`science` / `eval` 只在 tag（`v*`）或 `workflow_dispatch` 时跑，**常规 push/PR 只跑 `test`**——这样没有 self-hosted runner 时 `test` 仍能保持绿色，重 job 不会无限排队。

要启用 `science` / `eval`：在一台有 delivery bundle 的机器上注册 runner 并打标签 `self-hosted, linux, science`，再设仓库 secret `DELIVERY_BUNDLE_PATH`（指向 `rhobind_agent_delivery` 绝对路径）与可选 `NANOBOT_CONFIG_PATH`。详见 [RELEASE.md §9](RELEASE.md)。

---

## 5. 常见问题

- **`doctor` 报 AF3 deferred/broken**：正常。AF3 在某些 GPU（Blackwell/Triton）需更新 jax。AFDB 路径仍可用，`use_af3` 默认 `false`。重跑 `bash scripts/setup_all.sh`（AF3 harden 10 分钟预算）。
- **`onboard` 后 chat 仍报无 key**：确认 `~/.nanobot/config.json` 存在且 `chmod 600`；检查 `NANOBOT_CONFIG` 是否指向它。
- **CI 跳过 own-head/LOO**：public CI 无 GPU/delivery bundle。本地跑 `bash scripts/ci_gate.sh` 或 `rbp-agent gate`。
- **docs/ 大部分文件不在 clone 里**：`.gitignore` 默认忽略 `docs/`，仅跟踪子集（proposal、delivery要求、checklists、工程指南）。需要完整 docs 时从协作方处拷贝。
