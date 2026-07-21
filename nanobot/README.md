# `nanobot/` (plugin SoT)

**English** | [中文](README.zh.md)

Source of truth for the RBP agent **plugin overlay**: skills and tool implementations synced into the Nanobot Runtime (`$NANOBOT_SRC`) and the application workspace. This directory is not a full HKUDS/nanobot checkout.

## Purpose

Keep agent playbooks and tool wrappers editable in-repo while the framework dependency remains external—similar to how Transformers keeps *task heads* separate from core modeling, or how Nextflow modules are published independently of the engine.

## Contents

```text
nanobot/
├── skills/rbp-agent/SKILL.md      # Stage 0–3 playbook (edit here)
└── agent/tools/rbp/               # Tool implementations (edit here)
    ├── predict.py, catalogue.py, seq.py, rna_similarity.py
    ├── structure.py, annotation.py, evolve_tools.py
    ├── common.py, register.py, __init__.py
```

## Sync

```bash
python -m rbp_agent.sync_overlay
# or
rbp-agent doctor
```

Destinations: `$NANOBOT_SRC/agent/tools/rbp/`, `$NANOBOT_SRC/skills/rbp-agent/`, `workspace/skills/rbp-agent/`.

## Constraints

- Overlay root must not contain framework modules (`__init__.py`, `nanobot.py`, providers, …); enforced by `rbp-agent layout`.
- `import nanobot` must resolve to `$NANOBOT_SRC`, not this overlay tree.
- Do not hand-edit `workspace/skills/` copies (`DO_NOT_EDIT.md`).

## Related

[../README.md](../README.md) · [agent/tools/rbp/](agent/tools/rbp/README.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md)
