# Changelog

Changes to the RBP Agent application (`nanobot-bio`). Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.0] — 2026-07-23

### Added

- Final delivery alignment: `include_raw_delivery=all`; `check_near_known`; dual-axis `hits_emb`/`hits_seq`; AF3 `regions`; `function_category` in annotation; abstain-before-predict guards.
- App-side `mmseqs_wrap.sh` for `rna_blastn` / `protein_seq_similarity` (injects `--threads` without editing delivery).
- Eval helpers: `rbp_eval/{accept_llm,gap_closure,heavy_loo,rna_fm_gate}.py`; worklog under `docs/worklog/`.

### Changed

- **Layout:** product packages are `app/` + `plugin/nanobot/` SoT only; removed dual trees `rbp_agent/` and in-repo `nanobot/` overlay.
- Product README (EN/ZH): final full-open toolkit; fuse → abstain → predict; honest calibration (no fake online `score_calibration`).
- SKILL / Stage tool sets: `confidence_abstain` post-fuse / pre-predict (BUILD_SPEC).

### Fixed

- mmseqs all-core segfault path (`World Size: … dbSize: …`) via App wrap + `DeliveryToolClient` wiring.

## [0.3.0] — 2026-07-21

### Added

- **Layout:** `rbp_app` → `app/`; SoT → `plugin/nanobot/`; runtime data → `~/.nanobot-bio/{workspace,artifacts}`; added `AGENTS.md` / `CONTRIBUTING.md`.
- Proposal-anchored change gates (`docs/工程指南.zh.md` §9 / §9.10) and Cursor rule
- `config/defaults.yaml` `models:` metadata; doctor writes `model_capability_matrix.json`
- Agent-local `rna_similarity` (mock by default); ESM disk cache under `artifacts/cache/esm/`
- `evolve-eval`, evaluation-plan strata, Stage-3 checklist enforcement in `normalize_verdict`
- Product README rewrite (EN/ZH); proposal PDF/DOCX kept external (not required in-repo)

### Changed

- **Product CLI surface:** user commands are `doctor|onboard|agent|chat`; maintainer tools under `rbp-agent dev …`. Removed `mvp` acceptance entry.
- **App package renamed** `rbp_agent` → **`app`** (application shell only). `workspace/` and `artifacts/` live under `app/` only (repo-root compat symlinks removed).
- Single plugin SoT at repo-root `nanobot/`; removed `_proposal_sot` packaging tree
- Workspace skill sync prefers symlink to SoT; `fusion.py` shim removed (`fuse_hits` only)
- Default `rna_*` fusion weights set to 0 until a real RNA-FM checkpoint is configured
- `Nanobot.run` eval/MVP path supports `ephemeral=True`; `AgentResult` surfaces `tools_used` / `usage`

### Fixed

- Layout/compliance tests for SoT paths and proposal document presence
- Stale `__editable__.nanobot_bio-*.pth` cleanup pattern in setup
## [0.2.0] — 2026-07-20

### Added

- Layer documentation: App / SoT / Eval / Runtime / Science; installation entry `setup_all.sh`
- Chat UX; multi-vendor `onboard`; light LOO / eval-plan / evolve / evolve-eval
- Engineering Phase 1: `requirements.lock`, ruff/pytest-cov, `rbp-agent gate`, CI, doctor JSON, secret scan
- Offline evolution workflow: candidate → gate → promote; TraceEvent schema; axes hard-gate

### Changed

- Plugin overlay under `nanobot/`; full framework only at `$NANOBOT_SRC`
- `scripts/` limited to setup and gate helpers (acceptance under `app.dev`)
- Documentation consolidated into `docs/工程指南.zh.md`

### Fixed

- Foldseek / seq_similarity alias-only / disabled `web_search` error handling

## [0.1.0] — 2026-07-18

### Added

- Initial application: `rbp-agent` CLI, delivery bridge, RBP tools, skills via `Nanobot.run`

[0.4.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/releases/tag/v0.1.0
