# Changelog

All notable changes to **nanobot-bio** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-07-20

### Added

- Light vs heavy activate path; `setup_all.sh` default science conda stack
- Nanobot runtime ensure/sync helpers (`ensure_nanobot_runtime.sh`, skip-if-fresh install)
- Chat UX aligned with nanobot (folded thinking, prompt toolkit)
- `seq_similarity` resolves catalogue sequence from `alias` / `uniprot` / `query`
- Redirect stubs for `web_search` / `web_fetch` → use `literature_search`
- Optional AF3 accelerated env helper (does not modify delivery)

### Changed

- Slim package to proposal §6.2 overlay; full nanobot is a sibling runtime
- `DeliveryToolClient` uses absolute conda Python, sanitizes agent venv leak, prepends env `bin` for Foldseek/MMseqs
- Device resolution prefers CUDA without eager `torch` import at chat start
- Multi-vendor `rbp-agent onboard`
- README / docs refreshed for GitHub release layout
- Removed host-specific absolute paths from defaults (use `CONDA_ENVS_PATH` / `HF_HOME`)

### Fixed

- `struct_similarity` Foldseek `FileNotFoundError` when calling env Python directly
- `seq_similarity` “sequence required” when only alias was provided
- Clear error when models call disabled `web_search`

## [0.1.0] — 2026-07-18

### Added

- Initial private agent package: CLI (`rbp-agent`), delivery bridge, RBP tools, skills
- Product path via `Nanobot.run` + workspace skill
- Onboard / doctor / own-head / agent entrypoints

[0.2.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/JoeSun-421/rbp-nanobot-bio/releases/tag/v0.1.0
