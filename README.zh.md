# nanobot-bio

RNA–RBP **智能体**：嵌套 `nanobot/` + 只读 `rhobind_agent_delivery/`。

## 快速开始

```bash
export BIO_ROOT=/path/to/bio_agent
source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh
pip install -e $BIO_ROOT/nanobot-bio
rbp-agent onboard
rbp-agent doctor
```

科学 conda：delivery 的 `agent/setup_envs.sh`（`protein_embed` / `rna` / `rhobind`；AF3 可选）。
RhoBind 建议内存 ≥ 8–16 GiB。

## 行为

- **Stage 0（目录内 RBP）**：`resolve_rbp` → own-head `predict_interaction` 一次 → JSON → **停止**
- **未见 RBP**：检索 → donor 预测 → integrate → JSON
- 产品路径只有 `Nanobot.run`；固定 `core/pipeline` 已删除
- 禁止伪造 `p_hat`；predict OOM/超时：`p_hat=null`，不重试
- 禁止提交 API key

## 验收 / E2E（理想科学环境）

科学 golden 以 delivery
[`agent/examples/README.md`](../rhobind_agent_delivery/agent/examples/README.md)
为准（own-head ≈ **0.966**，AUPRC 0.9311）。

```bash
# Case 1 — own-head（无 LLM）
rbp-agent own-head
# PASS: prob ≈ 0.966 ± 0.05

# Case 1 — 经 Nanobot agent
rbp-agent agent --example pos --strict
# JSON: label=Strong, p_hat≈0.966；工具序 resolve_rbp → predict_interaction → STOP

rbp-agent chat
```

```bash
# Case 2 — 未见 / 强制 transfer
rbp-agent agent --message "..." --force-transfer
```

```bash
# Case 3 — delivery 原厂对照（无 nanobot）
bash $DELIVERY_ROOT/agent/examples/run_example.sh cpu
```
