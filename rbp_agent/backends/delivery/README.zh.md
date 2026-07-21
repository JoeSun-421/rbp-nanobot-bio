# `rbp_agent.backends.delivery`

[English](README.md) | **中文**

应用层到 **`rhobind_agent_delivery`** 的只读桥接。RhoBind、ESM、Foldseek、AF3、registry 与 LOO 先验均经 JSON 工具信封，在对应 conda 环境中执行。

## 目的

将科学内核与 agent 虚拟环境隔离，对应 Nextflow process、Snakemake conda、Transformers pipeline backend 等成熟隔离模式。

## 职责

1. 解析 `$DELIVERY_ROOT` 并注入路径变量。
2. 逻辑工具名 → 脚本（`SCRIPT_MAP` / `mapping.yaml`）。
3. 在正确 conda 解释器中执行并隔离环境。
4. 注册 curated 工具与 Stage 白名单 raw 工具。
5. payload 归一化（如为 `confidence_abstain` 注入演进阈值）。

## 主要文件

| 文件 | 作用 |
|------|------|
| `client.py` | `DeliveryToolClient`、`SCRIPT_MAP` |
| `env.py` | `apply_delivery_env` |
| `registry.py` | 白名单与归一化 |
| `stage_tools.py` | Stage 集合与轴门控 |
| `mapping.yaml` | 与 `SCRIPT_MAP` 对照表 |

## 约束

- 不得从本包修改 delivery 源码。
- 优先使用绝对 conda Python；必要时隔离 agent `site-packages`。
- 结构失败不得记为相似度 0。

## 相关

[../../README.zh.md](../../README.zh.md) · [../../../docs/工程指南.zh.md](../../../docs/工程指南.zh.md)
