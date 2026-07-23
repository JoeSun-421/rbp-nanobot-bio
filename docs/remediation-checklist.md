# Remediation checklist (Delivery × Proposal × this repo)

> **Audience:** Delivery / partner acceptance.  
> **Authoritative twin:** [`整改清单.zh.md`](整改清单.zh.md) (keep EN in sync with ZH + `config/defaults.yaml`).  
> **Sources:** [`delivery要求.zh.md`](delivery要求.zh.md), [`proposal.md`](proposal.md) / [`proposal.zh.md`](proposal.zh.md), [`工程指南.zh.md`](工程指南.zh.md) §9.  
> **Code baseline:** tag `v0.4.0`; reviewed 2026-07-23 (axes synced 2026-07-23).  
> **Tone:** factual status only. Tool authority: `$DELIVERY_ROOT/agent/tools/registry.json`.

| Tag | Meaning |
|-----|---------|
| DONE | Implemented in this repo |
| PARTIAL | Partially met; see gap |
| GAP | Not met vs baseline |
| OUT | Explicitly v2 / out of App scope |

---

## 1. Architecture

| ID | Requirement | Status | Location | Gap / action |
|----|-------------|--------|----------|--------------|
| A1 | Three layers: Controller / Toolkit / Predictor | DONE | `app/` + `nanobot/` + delivery subprocess | — |
| A2 | LLM agent orchestration (not fixed DAG) | DONE | `Nanobot.run` / `run_streamed`; CLI `nanobot-bio agent\|chat` | — |
| A3 | Do not edit delivery sources | DONE | read-only `DeliveryToolClient` | Verify no diffs under `rhobind_agent_delivery/` |
| A4 | Science torch outside nanobot process | DONE | conda envs | — |
| A5 | Single skill SoT | DONE | `nanobot/skills/rbp-agent/SKILL.md` | Do not hand-edit synced workspace copy |

## 2. Delivery control flow (BUILD_SPEC)

| ID | Requirement | Status | Gap / action |
|----|-------------|--------|--------------|
| D1 | In-panel own-head → STOP | DONE | `accept-golden` |
| D2 | Unseen: characterize → retrieve → fuse → abstain → predict → integrate | DONE | `accept-llm` / `gap-closure` |
| D3 | Dual seq axes `hits_emb` + `hits_seq` | DONE | — |
| D4 | Two LLM touchpoints | DONE | — |
| D5 | Integrate E1–E4 + evidence table → JSON | DONE | Abstain is pre-predict |
| D6 | All `status:ready` tools discoverable | DONE | Curated aliases may differ from registry names |
| D7 | OOD abstain + hedge | DONE | — |

## 3. Proposal Table 2 / 3

| ID | Requirement | Status | Gap / action |
|----|-------------|--------|--------------|
| P1 | P0 tools | DONE | — |
| P2 | P1 structure / function | DONE | Default `axes.structure=true` (AFDB preferred) |
| P3 | P2 AF3 / literature | PARTIAL | `literature=true`; `use_af3=false` until probe green |
| P4 | \(N_{\mathrm{cand}}=5\), \(\tau_{\mathrm{drop}}=0.30\) | DONE | — |
| P5 | Label cuts 0.75 / 0.50 / 0.25 | DONE | — |
| P6 | Near-known ≥95% | DONE | — |
| P7 | Verdict fields | DONE | \(\hat{p}\) is **raw**, not calibrated P(bind) |
| P8 | nanobot + skill | DONE | — |

## 4. Calibration wording

| ID | Status | Fact |
|----|--------|------|
| C1 | PARTIAL | `p_hat` = predictor/vote raw; `confidence` = rules + checklist |
| C2 | OUT | `score_calibration` is Delivery v2 (not in registry) |
| C3 | DONE | LOO priors / donor quality / abstain thresholds |
| C4 | PARTIAL | Threshold retune path exists; defaults locked to Table 3 |

## 5. Eval / self-evolution

| ID | Status | Gap / action |
|----|--------|--------------|
| E1–E4 | PARTIAL | Commands exist; full-panel numbers only if reports present |
| E5 | DONE | Offline promote only |
| E6 | DONE | `lookup_proxy_cache` |

## 6. Host facts (this machine)

| Item | Fact |
|------|------|
| Default axes | `structure` / `rna_blastn` / `literature` = **true**; `use_af3` = **false** (AFDB preferred) |
| AF3 | See `.af3_status` (`ok` / `deferred` / `broken`); agent uses AFDB when not `ok` |
| RNA-FM | mock without checkpoint; fusion weights 0 |
| Docs | Key dual-SoT files tracked (`proposal*`, checklists, `工程指南.zh.md`, `delivery要求.zh.md`) |

## 7. Acceptance commands

```bash
cd nanobot-bio && source .venv/bin/activate
nanobot-bio doctor
nanobot-bio accept-golden
nanobot-bio accept-llm
nanobot-bio gap-closure
pytest tests/test_proposal_compliance.py -q
```

Reports: `artifacts/reports/` (or `~/.nanobot-bio/artifacts/reports/` when overridden).
