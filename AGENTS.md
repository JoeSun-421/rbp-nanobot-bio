# Agent / CI constraints (nanobot-bio)

**Source of truth:** [`docs/工程指南.zh.md`](docs/工程指南.zh.md) §9 (local-only). Chat agreements do **not** override these rules. This file is the committed short gate for agents and CI.

## MUST NOT

- Edit `rhobind_agent_delivery/` — science only via App bridge.
- Call \(f_\theta\) / `predict_interaction` on an **unseen** target without proxy donors; invent `p_hat` / `prob` with the LLM; treat AF3/structure miss as similarity `0`.
- Change Table 3 defaults without eval evidence + `config/defaults.yaml` + `tests/test_proposal_compliance.py`.
- Online weight writes / auto-edit delivery registry; promote evolved config without gate + nested-split (`delta_auprc > 0` or HOLD).
- Add a third tools tree (edit `nanobot/` SoT only); give mock RNA-FM fusion weight; commit secrets / push `docs/`; import science torch into the nanobot process; add LangGraph/CrewAI/AutoGen as product deps.

## MUST

- Layers: Agent Controller (in-repo slim `nanobot/`) / Toolkit / Predictor + offline `rbp_eval/`.
- Product path: `Nanobot.from_config` → `run` / `run_streamed` (`nanobot-bio agent|chat`). Prefer `ephemeral=True` for MVP/eval. Do not install `nanobot-ai`.
- Stage 0→1→2→3 + two LLM checkpoints; Stage 0 own-head / near-known Fast Path; \(N_{\mathrm{cand}}\le5\); drop fused similarity \(<0.30\).
- Tool contract: JSON Schema, error envelope, `latency_ms`, retrieve tools `read_only=True`.
- Skill SoT: `nanobot/skills/rbp-agent/SKILL.md`. Model metadata in `config/defaults.yaml` → `models:`.

## After edits

```bash
pytest tests/test_proposal_compliance.py
```

Full fidelity notes (AF3 / ESM-C / fuse / `p_hat` wording): 工程指南 §9 + proposal §4.
