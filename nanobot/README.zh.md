# `nanobot/`（插件 SoT）

[English](README.md) | **中文**

RBP agent **插件覆盖层**的源码真相：skill 与工具实现，同步至 Nanobot Runtime（`$NANOBOT_SRC`）与应用 workspace。本目录不是完整 HKUDS/nanobot。

## 目的

在仓内可编辑 playbook 与工具封装，框架依赖保持外置——类似 Transformers 任务头与核心建模分离、Nextflow 模块与引擎分离。

## 内容

```text
nanobot/
├── skills/rbp-agent/SKILL.md      # Stage 0–3（仅在此编辑）
└── agent/tools/rbp/               # 工具实现（仅在此编辑）
```

## 同步

```bash
python -m rbp_agent.sync_overlay
rbp-agent doctor
```

目标：`$NANOBOT_SRC/agent/tools/rbp/`、`$NANOBOT_SRC/skills/rbp-agent/`、`workspace/skills/rbp-agent/`。

## 约束

- 覆盖层根不得出现框架模块；由 `rbp-agent layout` 检查。
- `import nanobot` 须指向 `$NANOBOT_SRC`。
- 勿手改 `workspace/skills/` 副本。

## 相关

[../README.zh.md](../README.zh.md) · [agent/tools/rbp/](agent/tools/rbp/README.zh.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md)
