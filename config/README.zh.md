# `config/`

[English](README.md) | **中文**

融合权重、abstain / 标签阈值、integrate / predict 与结构轴等运行时 YAML。由 `app.core.runtime_config` 及相关工具读取。

## 文件

| 文件 | 作用 | 写入方 |
|------|------|--------|
| `defaults.yaml` | 基线 | 人工 / 发版 |
| `evolved.candidate.yaml` | 离线 evolve 候选 | `rbp-agent evolve` |
| `evolved.yaml` | 生效配置（`evolved: true`） | `rbp-agent promote-evolved` |

## 语义

- 仅当 `evolved: true` 时合并 live 配置。
- 融合权重显式 `0.0` 表示关闭该模态，不得回退默认值。
- abstain 阈值注入 `confidence_abstain`，除非调用方覆盖。

## 相关

[../README.zh.md](../README.zh.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md) §4.5
