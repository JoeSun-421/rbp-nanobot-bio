# `workspace/`

**English** | [中文](README.zh.md)

Directory passed to `Nanobot.run(workspace=…)` (default `$NANOBOT_WORKSPACE`). Holds skills, memory, and session pointers. Evaluation reports and structure caches belong under `artifacts/` (cf. separation of *project home* vs *results* in Nextflow/Snakemake layouts).

## Layout

```text
workspace/
├── AGENTS.md
├── skills/rbp-agent/SKILL.md   # synced copy — do not hand-edit
├── memory/                     # gitignored contents
└── sessions -> ../artifacts/sessions
```

## Skill editing

| Location | Editable? |
|----------|-----------|
| `plugin/nanobot/skills/rbp-agent/SKILL.md` | Yes (SoT) |
| `workspace/skills/rbp-agent/SKILL.md` | No (sync copy) |

```bash
python -m app.sync_overlay
nanobot-bio doctor
```

Restart chat after skill changes.

## Related

[../README.md](../README.md) · [../artifacts/](../artifacts/README.md) · [../nanobot/](../nanobot/README.md)
