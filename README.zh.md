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

## 项目简介

nanobot-bio 是一个命令行 Agent，用来估计一段 RNA 与某个 RBP（RNA-binding protein）是否可能结合，以及结合强弱大致如何。

本仓库是 Agent 层（CLI、工具、对话与 verdict）。数值分数来自同级科学工具包 `rhobind_agent_delivery`（只读 bridge）。LLM 负责规划工具调用与解释，不编造 `p_hat`。

输出为 JSON verdict（`label`、`confidence`、`p_hat`、`explanation`、`supporting_rbps`）。

- **Panel 内 RBP**：`resolve_rbp` → 一次 `predict_interaction`（own head）→ verdict。
- **未见 RBP**：检索 donor → 在其预测头上打分 → 融合 → verdict。

安装细节、环境变量、Docker 与验收见 [INSTALL.md](INSTALL.md)。

## 快速开始

环境：推荐 Linux x86_64，Python ≥ 3.10，`rhobind_agent_delivery` 与本仓库同级，并准备 LLM API key。

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

bash scripts/setup_all.sh
source .venv/bin/activate
nanobot-bio onboard
nanobot-bio doctor
nanobot-bio chat
```

不要 `pip install nanobot-ai`（会与仓内 `nanobot/` 冲突）。只要 agent 层可用：`bash scripts/setup_all.sh --skip-conda`。

## 使用方式

| 命令 | 说明 |
|------|------|
| `nanobot-bio onboard` | 配置 LLM 与 API key |
| `nanobot-bio doctor` | 检查路径与就绪状态 |
| `nanobot-bio agent --message "..."` | 一次性预测 |
| `nanobot-bio chat` | 多轮对话 |

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <sequence>"
nanobot-bio chat
```

对话内：`/help` · `/status` · `/tools` · `/new` · `/quit`。提问时写清 RBP 名称和 RNA 序列。

verdict 示例：

```json
{
  "label": "Strong",
  "confidence": "high",
  "p_hat": 0.966,
  "explanation": "...",
  "supporting_rbps": ["PTBP1"]
}
```
