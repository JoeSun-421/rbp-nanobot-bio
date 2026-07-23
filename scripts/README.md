# `scripts/`

**English** | [中文](README.zh.md)

Installation and engineering-gate helpers for **nanobot-bio**. Acceptance logic lives under `app.dev` (CLI: `nanobot-bio accept-golden|accept-llm|gap-closure|layout|gate`).

| Script | Role |
|--------|------|
| `setup_all.sh` | Install App venv, optional science conda, SoT sync, AF3 status |
| `ci_gate.sh` | Wrapper → `rbp-agent gate` |
| `check_secrets.sh` | Scan tracked files for committed secrets |

## `setup_all.sh`

1. Ensure Nanobot Runtime at `$NANOBOT_SRC` (clone if missing).  
2. Optionally build science conda via delivery `setup_envs`.  
3. Create `.venv`, install `requirements.lock`, then `pip install -e ".[dev]"`.  
4. Write `.env` stubs, create `artifacts/`, sync plugin SoT.  
5. Optional AF3 status / budget (`AF3_BUDGET_SEC`).  
6. Smoke: `rbp-agent doctor` unless `--skip-smoke`.

```bash
export BIO_ROOT=/path/to/workspace
bash scripts/setup_all.sh
source .venv/bin/activate
rbp-agent doctor && rbp-agent layout
```

| Flag / env | Effect |
|------------|--------|
| `--skip-conda` | Skip science conda |
| `--skip-af3` | Skip AF3 checks |
| `--skip-smoke` | Skip doctor |
| `NANOBOT_SRC` / `DELIVERY_ROOT` | Path overrides |

Delivery sources are never modified.

## Gates

```bash
bash scripts/ci_gate.sh
rbp-agent gate --skip-eval
bash scripts/check_secrets.sh
```

Public CI: [../.github/workflows/ci.yml](../.github/workflows/ci.yml).

## Related

[../README.md](../README.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md)
