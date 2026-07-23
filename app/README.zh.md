# `app`

[English](README.md) | **中文**

**nanobot-bio** 的应用包：CLI（`rbp-agent`）、Nanobot 集成、delivery 桥接、验收与插件 SoT 同步。插件源位于仓根 [`nanobot/`](../nanobot/)，不并入本包。

## 目的

提供可安装、可调用的产品面。科学内核仍外置于 delivery，类似 Scanpy 用户 API 与底层数值库的分工。

## 范围

| 包含 | 不包含 |
|------|--------|
| `cli.py`、`integrate.py`、sync、backends、acceptance | 完整 Nanobot 框架源码 |
| 运行时配置合并与终端交互 | 修改 delivery registry 或权重 |

## 布局

```text
app/
├── cli.py              # 子命令入口
├── integrate.py        # Nanobot.run + 工具注册
├── sync_overlay.py     # SoT → Runtime / workspace
├── sot.py / dotenv_util.py
├── core/               # 路径、onboard、UX、runtime_config、verdict
├── backends/delivery/  # 只读科学桥
├── acceptance/         # layout / gate / own-head / mvp / compliance
└── backends/           # delivery + rna_fm
```

## 对外接口

| 入口 | 作用 |
|------|------|
| `rbp-agent …` | 主 CLI |
| `integrate` / `RBPAgent` | 程序化 `Nanobot.run` |
| `python -m app.sync_overlay` | 同步覆盖层 |

## 设计说明

- 科学调用仅经 `backends.delivery`。
- `p_hat` 与 verdict 规范化在 `core.verdict_schema`。
- 仅当 `evolved: true` 时合并 live 演进配置。

## 相关

[../README.zh.md](../README.zh.md) · [core/](core/README.zh.md) · [backends/delivery/](backends/delivery/README.zh.md) · [acceptance/](acceptance/README.zh.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md)
