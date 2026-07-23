# `app.core`

[English](README.md) | **中文**

应用层共享模块：产物路径、LLM onboard、终端交互、运行时配置合并、verdict JSON schema。

## 模块

| 文件 | 职责 |
|------|------|
| `paths.py` | `artifacts/` 子目录权威定义与会话软链 |
| `onboard.py` | 多厂商 LLM → `~/.nanobot/config.json` |
| `chat_ux.py` | 终端展示（thinking 折叠、提示、资源提示） |
| `runtime_config.py` | 合并 `defaults.yaml` 与 live `evolved.yaml` |
| `verdict_schema.py` | 最终 JSON 校验与规范化 |

## 设计说明

可写产物集中于单一根目录，对应 Nextflow publishDir、Snakemake results、HF `cache_dir` 等成熟约定。

## 相关

[../README.zh.md](../README.zh.md) · [../../config/](../../config/README.zh.md) · [../../docs/工程指南.zh.md](../../docs/工程指南.zh.md)
