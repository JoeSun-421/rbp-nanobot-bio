# `nanobot.agent.tools.rbp`

[English](README.md) | **中文**

面向 RNA–RBP 评估的 Nanobot `Tool` 实现。类可被插件发现（`_plugin_discoverable = True`），经 `register_all` / delivery 白名单注册。

## 目的

向 LLM 提供稳定工具面；数值输出仍来自 delivery 或 agent-local 辅助（如 `rna_similarity`），类似 Transformers pipeline 对模型调用的封装。

## 工具摘要

| 工具 | 作用 |
|------|------|
| `predict_interaction` | RhoBind |
| `seq_similarity` | ESM-C |
| `rna_similarity` | RNA 嵌入 / bank（agent-local） |
| `struct_similarity` / `predict_structure` | Foldseek / AF3 |
| `get_func_annotation` / `literature_search` | 功能 / 文献 |
| `lookup_proxy_cache` / `fuse_similarity_views` | 缓存与融合 |
| Redirect stubs | 禁用 shell / 通用网络 / 文件系统工具 |

## 编辑

仅在本 SoT 目录修改，随后：

```bash
python -m rbp_agent.sync_overlay
```

## 约束

- 不得虚构 `p_hat`。
- 结构失败 ≠ 相似度 0；见 [docs/工程指南.zh.md](../../../../docs/工程指南.zh.md) §8。

## 相关

[../../../README.zh.md](../../../README.zh.md)
