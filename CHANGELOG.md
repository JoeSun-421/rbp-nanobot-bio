# Changelog

Changes to the RBP Agent application (`nanobot-bio`). Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] — 2026-07-21

### Added

- Proposal-anchored change gates (`docs/工程指南.zh.md` §9 / §9.10) and Cursor rule
- `config/defaults.yaml` `models:` metadata; doctor writes `model_capability_matrix.json`
- Agent-local `rna_similarity` (mock by default); ESM disk cache under `artifacts/cache/esm/`
- `evolve-eval`, evaluation-plan strata, Stage-3 checklist enforcement in `normalize_verdict`
- Product README rewrite (EN/ZH); proposal PDF/DOCX kept external (not required in-repo)

### Changed

- Single plugin SoT at repo-root `nanobot/`; removed `_proposal_sot` packaging tree
- Workspace skill sync prefers symlink to SoT; `fusion.py` shim removed (`fuse_hits` only)
- Default `rna_*` fusion weights set to 0 until a real RNA-FM checkpoint is configured
- `Nanobot.run` eval/MVP path supports `ephemeral=True`; `AgentResult` surfaces `tools_used` / `usage`

### Fixed

- Layout/compliance tests for SoT paths and proposal document presence

## [0.2.0] — 2026-07-20

### Added

- Layer documentation: App / SoT / Eval / Runtime / Science; installation entry `setup_all.sh`
- Chat UX; multi-vendor `onboard`; light LOO / eval-plan / evolve / evolve-eval
- Engineering Phase 1: `requirements.lock`, ruff/pytest-cov, `rbp-agent gate`, CI, doctor JSON, secret scan
- Offline evolution workflow: candidate → gate → promote; TraceEvent schema; axes hard-gate

### Changed

- Plugin overlay under `nanobot/`; full framework only at `$NANOBOT_SRC`
- `scripts/` limited to setup and gate helpers (acceptance under `rbp_agent.acceptance`)
- Documentation consolidated into `docs/工程指南.zh.md`

### Fixed

- Foldseek / seq_similarity alias-only / disabled `web_search` error handling

## [0.1.0] — 2026-07-18

### Added

- Initial application: `rbp-agent` CLI, delivery bridge, RBP tools, skills via `Nanobot.run`

[0.3.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/releases/tag/v0.1.0
