# `app`

**English** | [中文](README.zh.md)

Application package for **nanobot-bio**: CLI (`rbp-agent`), Nanobot integration, delivery bridge, acceptance checks, and plugin SoT synchronization. Plugin source remains at repository-root [`nanobot/`](../nanobot/) and is not merged into this package.

## Purpose

Provide the installable product surface that scientists and engineers invoke. Analogous to analysis entry packages in ecosystems such as Scanpy (user API) or Transformers (`pipeline` / CLI), while scientific kernels remain external (delivery).

## Scope

| Included | Excluded |
|----------|----------|
| `cli.py`, `integrate.py`, sync, backends, acceptance | Full Nanobot framework sources |
| Runtime config merge and chat UX | Editing delivery registries or weights |

## Layout

```text
app/
├── cli.py              # argparse subcommands → rbp-agent
├── integrate.py        # Nanobot.run + tool registration
├── sync_overlay.py     # SoT → $NANOBOT_SRC + workspace
├── sot.py              # locate plugin SoT
├── dotenv_util.py      # load .env
├── core/               # paths, onboard, chat UX, runtime_config, verdict schema
├── backends/delivery/  # read-only science bridge
├── acceptance/         # layout, gate, own-head, mvp, compliance
└── backends/           # delivery + rna_fm
```

## Public interface

| Entry | Role |
|-------|------|
| `rbp-agent …` | Primary CLI ([`cli.py`](cli.py)) |
| `RBPAgent` / `integrate` | Programmatic `Nanobot.run` |
| `python -m app.sync_overlay` | Sync plugin overlay |

## Design notes

- Delivery is accessed only through `backends.delivery`.
- `p_hat` validation and verdict normalization live in `core.verdict_schema`.
- Evolved knobs load via `core.runtime_config` when `evolved: true`.

## Related

- [../README.md](../README.md) · [core/](core/README.md) · [backends/delivery/](backends/delivery/README.md) · [acceptance/](acceptance/README.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md)
