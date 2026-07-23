# `app.acceptance`

[English](README.md) | **中文**

由 `rbp-agent` 子命令调用的验收与合规检查。以可 import 模块替代纯 shell 门禁，便于测试与 CI（参见 Transformers / Lightning / ruff 等仓库的测试组织方式）。

## 模块 ↔ CLI

| 模块 | CLI | 检查内容 |
|------|-----|----------|
| `layout.py` | `layout` | 覆盖层路径；`import nanobot` → Runtime |
| `gate.py` | `gate` | ruff + pytest + layout；可选 light LOO / eval-plan |
| `own_head.py` | `own-head` | PTBP1 金标 ≈ 0.966（无 LLM） |
| `mvp.py` | `mvp` | 端到端 `Nanobot.run` |
| `compliance.py` | `compliance` | delivery 路径 / SCRIPT_MAP |

## 推荐顺序

新主机：**layout → doctor → own-head → mvp**。完整协议见 [../../docs/工程指南.zh.md](../../docs/工程指南.zh.md) §6。

## 相关

[../README.zh.md](../README.zh.md) · [../../tests/](../../tests/README.zh.md)
