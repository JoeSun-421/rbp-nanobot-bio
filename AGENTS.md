# Agent / CI constraints (nanobot-bio)

Executable gates: [`docs/工程指南.zh.md`](docs/工程指南.zh.md) §9. Chat agreements do **not** override these rules.

## MUST NOT

- Edit `rhobind_agent_delivery/` (registry, weights, scripts). Science only via App bridge.
- Call \(f_\theta\) / `predict_interaction` on an **unseen** target without proxy donors.
- Invent `p_hat` / `prob` with the LLM. On OOM/timeout emit `p_hat=null`.
- Treat structure/AF3 failure as similarity `0`. Fall back to sequence/domain; keep confidence low.
- Change Table 3 defaults without eval evidence + updating `config/defaults.yaml` and `tests/test_proposal_compliance.py`.
- Online weight writes or auto-edit delivery registry. Self-evolution is **offline** only.
- Promote evolved config without gate + nested-split evidence (`delta_auprc > 0` or HOLD).
- Add a third tools tree. Edit only `nanobot/` SoT; workspace skill is a sync copy.
- Give mock RNA-FM fusion weight (`rna_embed` / `rna_fm` stay 0 until a real `RNA_FM_CHECKPOINT`).
- Commit API keys, `.env`, or `~/.nanobot/config.json`.
- Import science torch into the nanobot process; keep conda/subprocess isolation.
- Introduce LangGraph/CrewAI/AutoGen as product dependencies.

## MUST

- Three layers: Agent Controller (nanobot) / Toolkit / Predictor + offline Validation Evaluator.
- Product path: `Nanobot.from_config` → `run` / `run_streamed` (`nanobot-bio agent|chat`). Prefer `ephemeral=True` for MVP/eval.
- Stage 0→1→2→3 semantics and **two LLM checkpoints**. Deterministic `fuse_*` baseline allowed.
- Stage 0: strict UniProt match → own-head once then STOP; identity ≥95% → near-known Fast Path.
- Cap \(N_{\mathrm{cand}}\le5\); drop fused similarity \(<0.30\).
- Tool contract: JSON Schema, error envelope, `latency_ms`, `read_only=True` for retrieve tools.
- Stage-3: checklist failures ≥2 → force `confidence=low` in `normalize_verdict`.
- Skill SoT: `nanobot/skills/rbp-agent/SKILL.md`. Scientific claims need `eval-plan` / `evolve-eval` report paths.
- Model metadata in `config/defaults.yaml` → `models:`.

## Implementation notes (proposal §4 fidelity)

- Structure: AFDB → Foldseek; AF3 fallback on AFDB miss (`use_af3` / `use_af3_fallback` default true).
- Sequence: ESM-C + MMseqs dual axes (not protein BLASTn).
- Aggregate: default `predict.aggregate: weighted` (proposal §4 \(\sum s\cdot p\cdot c\`); authoritative \(s_i\) from `commit_proxy_candidates`).
- Fuse: deterministic `fuse_similarity_views` is evidence; LLM Checkpoint 1 commits calibrated scores.
- `p_hat` is raw; do not claim calibrated P(bind).

## After edits

```bash
pytest tests/test_proposal_compliance.py
```
