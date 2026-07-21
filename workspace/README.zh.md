# `workspace/`

[English](README.md) | **中文**

`Nanobot.run(workspace=…)` 使用的目录（默认 `$NANOBOT_WORKSPACE`）。存放 skill、memory 与会话指针。评测报告与结构缓存位于 `artifacts/`（对应 Nextflow/Snakemake 中工作区与结果目录的分离）。

## 布局

```text
workspace/
├── AGENTS.md
├── skills/rbp-agent/SKILL.md   # sync 副本，勿手改
├── memory/
└── sessions -> ../artifacts/sessions
```

## Skill 编辑

| 位置 | 可编辑 |
|------|--------|
| `nanobot/skills/rbp-agent/SKILL.md` | 是（SoT） |
| `workspace/skills/rbp-agent/SKILL.md` | 否 |

```bash
python -m rbp_agent.sync_overlay
```

修改后需重启 chat。

## 相关

[../README.zh.md](../README.zh.md) · [../artifacts/](../artifacts/README.zh.md) · [../nanobot/](../nanobot/README.zh.md)
