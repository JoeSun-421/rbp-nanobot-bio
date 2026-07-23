# An Agentic Framework for Predicting RNA–RBP Interactions on Unseen Proteins

**Project Proposal**  
**Internal Working Document**  
**July 9, 2026**

> In-repo English source of the Internal Working Document (user-supplied full text, 2026-07-23). Full text: Abstract + §§1–11.  
> Chinese translation: [`proposal.zh.md`](proposal.zh.md).  
> Executable gates mirrored in [`工程指南.zh.md`](工程指南.zh.md) §9. PDF/DOCX are not required in-repo.  
> **Preview tip:** If Preview goes blank mid-doc, KaTeX likely stalled (file is not truncated)—use **source view**, or close and reopen Preview.

---

## Abstract

We propose an LLM-driven agent that extends a pre-trained RNA–RBP interaction classifier from a closed set of known RNA-binding proteins (RBPs) to arbitrary, previously-unseen RBPs. The agent uses a curated bioinformatics toolkit (sequence search, structure alignment, function annotation) to retrieve a small set of similar proxy RBPs from the training catalogue, runs the classifier on those proxies, and produces an interpretable interaction verdict by fusing the proxy probabilities with the per-proxy similarity evidence. The framework is implemented on top of nanobot, a lightweight agent runtime, and is designed to be self-evolving: the toolkit composition and fusion weights are periodically re-tuned against a held-out validation set.

---

## 1 Background and Motivation

The team has trained a multi-class interaction classifier \(f_\theta(\mathrm{RNA},\mathrm{RBP})\to[0,1]\) over a fixed catalogue of \(N_{\mathrm{known}}\) RNA-binding proteins. The classifier is accurate when the queried RBP lies in the training catalogue, but its support cannot be extended naively: training data for new RBPs is often unavailable, and retraining on every new target is impractical.

A natural workaround is to borrow strength from the closest analogues in the training catalogue: if the query RBP is highly similar to one or more known RBPs, then the classifier’s output on those analogues is informative for the query. Implementing this idea in a principled, interpretable, and extensible way requires more than a fixed pipeline—similarity itself is multi-faceted (sequence, structure, function), and the appropriate aggregation depends on the target. We therefore frame the system as an LLM agent that orchestrates a toolkit and produces a justified verdict.

---

## 2 Task Definition

**Input.**

- An RNA sequence \(r\in\Sigma^*_{\mathrm{RNA}}\).
- A target RBP \(p^\star\), identified by its UniProt ID and amino-acid sequence (and, when available, a 3D structure).

**Output.** A structured verdict

\[
V=\{\mathrm{label},\ \hat{p},\ \mathrm{confidence},\ \mathrm{explanation},\ \mathrm{supporting\ RBPs}\},
\]

where \(\mathrm{label}\) is one of \(\{\mathrm{Strong},\mathrm{Likely},\mathrm{Unlikely},\mathrm{No}\}\) and \(\hat{p}\) is the **raw** interaction score from the predictor / donor vote (not a post-hoc calibrated P(bind); Delivery v2 `score_calibration` is out of scope). Rule-based `confidence` and Stage-3 checklists hedge the verdict.

**Scope assumption.** We assume the team maintains a catalogue

\[
\mathcal{K}=\{(p_i,\mathrm{seq}_i,\mathrm{struct}_i,\mathrm{annot}_i)\}_{i=1}^{N_{\mathrm{known}}}
\]

of known RBPs with sequences, structures (AFDB cache preferred for \(\mathcal{K}\); AF3 only as optional fallback for novel targets), and function annotations.

---

## 3 System Architecture

### 3.1 High-Level Overview

The system is organised in three layers (Figure 1):

1. **Agent Controller (LLM):** parses the query, plans tool calls, fuses heterogeneous evidence, and writes the final explanation.
2. **Toolkit Layer:** a registry of bioinformatics tools exposed to the LLM via JSON-schema function-calling. Tools are stateless and grouped into three views—sequence, structure, and function.
3. **Predictor Layer:** the team’s pre-trained interaction classifier, also exposed as a tool, plus a memory/log component that records traces for offline self-evolution.

```text
User Query
(RNA seq, target RBP)
        │
        ▼
Agent Controller (LLM via nanobot)
Routing · Tool Scheduling · Evidence Fusion · Explanation
        │
   ┌────┼────┐
   ▼    ▼    ▼
Sequence   Structure   Function
ESM/MMseqs  AFDB/Foldseek(+AF3)  UniProt/Lit.
   │         │         │
   └────┬────┘─────────┘
        ▼
   Toolkit Layer
        │
        ▼
   Predictor
   fθ(RNA,RBP)
   Predictor Layer
        │
        ▼
Memory & Trace Log  ···(offline)···▶  Validation Evaluator
for self-evolution                    tool weights / additions
```

**Figure 1:** System architecture. Solid arrows: per-query call flow. Dashed arrows: offline trace logging and self-evolution feedback.

### 3.2 Why an Agent (not a Fixed Pipeline)

Two parts of the workflow demand the flexibility of an LLM, and were marked as such in the original sketch:

1. **Heterogeneous evidence fusion.** Function annotations are free text; combining them with numerical sequence/structure scores requires natural-language reasoning (e.g. “both contain RRM domains and act on pre-mRNA splicing”) rather than a hand-tuned weighted sum.
2. **Interpretable verdict.** Downstream users need to know why a prediction was issued. The LLM produces a faithful explanation grounded in the tool outputs it consumed, which a fixed pipeline cannot deliver.

---

## 4 Detailed Workflow

The agent’s per-query behaviour is divided into four stages.

### Stage 0 — Query Parsing and Fast Path

The agent extracts \(\{r,p^\star\}\) and checks \(p^\star\in\mathcal{K}\).

- **Strict match** (UniProt ID equality) ⇒ Fast Path: call the predictor once and return.
- **Near-match** (sequence identity ≥ 95% to some \(p_i\in\mathcal{K}\)) ⇒ Fast Path with the matched proxy, flagged in the explanation.
- **Otherwise** ⇒ proceed to Stage 1.

### Stage 1 — Multi-View Candidate Retrieval

The agent retrieves similar RBPs along three independent views in parallel.

| View | Tools | Output |
|------|-------|--------|
| Sequence | ESM-C embeddings + MMseqs (`hits_emb` / `hits_seq`) | Top-K catalogue RBPs with dual-axis scores; ESM for remote homology, MMseqs for identity. |
| Structure | AFDB `structure_fetch` → Foldseek; optional USalign refine; AF3 only if `axes.use_af3` and no AFDB hit | Top-K catalogue RBPs with TM / Foldseek scores. Structure failure ≠ similarity `0`. |
| Function | UniProt, PDB, literature search | Free-text annotations (GO terms, domains, function descriptions). |
| RNA (optional axis) | `rna_blastn` / RNA similarity | RNA-side hits when the axis is enabled. |

**Table 1:** Stage 1 retrieval views (as implemented vs Delivery). Calls run concurrently where possible; structure prefers AFDB and falls back to sequence/domain when structure tools fail (never encode failure as sim `0`).

**LLM fusion (first LLM checkpoint).** The agent then asks the LLM to merge the three candidate lists and the textual annotations into a ranked list of \(N_{\mathrm{cand}}=5\) proxy candidates, each annotated with:

```json
{
  "rbp_id": "P12345",
  "similarity_score": 0.78,
  "similarity_breakdown": {
    "seq": 0.82, "struct": 0.61, "func": 0.85
  },
  "rationale": "Shares an RRM domain with the target; both annotated as splicing factors; ESM cosine 0.81."
}
```

(`similarity_score` is in \([0,1]\), LLM-calibrated.)

The LLM is instructed to drop any candidate with a fused similarity below a configurable floor (\(\tau_{\mathrm{drop}}=0.30\)), so \(N_{\mathrm{cand}}\) is an upper bound, not a fixed quota.

### Stage 2 — Predictor Calls on Proxies

For each surviving candidate \(p_i\), the agent issues \(\hat{p}_i=f_\theta(r,p_i)\). Calls are independent and can be batched. The predictor tool returns:

```json
{
  "rbp_id": "P12345",
  "prob": 0.84,
  "confidence": 0.91,
  "feature_attribution": {}
}
```

(`feature_attribution` is optional, used for explanation.)

### Stage 3 — Aggregation and Explanation

**Numeric aggregation.** Product default is **`predict.aggregate: max`** over donor heads (Delivery integrate may still expose similarity-weighted vote as a tool). The classical similarity-weighted mean

\[
\hat{p}=\frac{\sum_{i=1}^{N_{\mathrm{cand}}} s_i\cdot\hat{p}_i\cdot c_i}{\sum_{i=1}^{N_{\mathrm{cand}}} s_i\cdot c_i}
\]

remains an offline evolve candidate, not the silent default. Transfer priors / donor quality / abstain gates run **before** the final explanation.

**Label thresholds.**

\[
\mathrm{label}=
\begin{cases}
\mathrm{Strong} & \hat{p}\ge 0.75 \\
\mathrm{Likely} & 0.50\le\hat{p}<0.75 \\
\mathrm{Unlikely} & 0.25\le\hat{p}<0.50 \\
\mathrm{No} & \hat{p}<0.25
\end{cases}
\]

Thresholds are re-calibrated on the validation set (§7).

**LLM explanation (second LLM checkpoint).** The LLM receives (\(p^\star\) annotation, \(\{(p_i,s_i,\hat{p}_i,c_i,\mathrm{rationale}_i)\}\)), and emits a single JSON object containing the verdict, supporting RBPs, and a concise (3–5 sentence) human-readable explanation. Caveats (e.g. “one high-similarity proxy disagreed”) are surfaced explicitly.

---

## 5 Tool Interface Specification

All tools follow nanobot’s Tool contract: a name, a description, a JSON-schema parameter spec, and an async `execute` method. Failures must return `{status: "error", reason: ...}` rather than raising, so the agent can fall back gracefully.

| Pri. | Tool | Purpose |
|------|------|---------|
| P0 | `predict_interaction(rna, rbp_id)` | Core classifier; returns raw prob / attributions. |
| P0 | `get_known_rbp_list()` / `resolve_rbp` | Catalogue \(\mathcal{K}\) + in-panel resolution. |
| P0 | `seq_similarity(target, candidates?)` | ESM-C + MMseqs dual axes (`hits_emb` / `hits_seq`). |
| P1 | `struct_similarity` / `structure_fetch` | Foldseek on AFDB (preferred); optional USalign refine. |
| P1 | `get_func_annotation` / `domain_architecture` | UniProt + PDB / domain textual annotation. |
| P1 | `fuse_similarity_views` / `confidence_abstain` | Multi-view fuse + OOD abstain (before predict on transfer). |
| P1 | `transfer_prior_lookup` / `donor_quality_prior` / `similarity_weighted_vote` | Delivery integrate E1–E4. |
| P2 | `predict_structure(seq)` | AF3 fallback when enabled and no AFDB structure. |
| P2 | `literature_search(rbp_name)` | Top-k abstracts to augment annotation. |

**Table 2:** Toolkit specification aligned with Delivery BUILD_SPEC. P0 required for demo; P1 full multi-view + integrate; P2 optional AF3 / literature.

**Shared conventions.**

- **IDs.** All proteins are addressed by UniProt accession.
- **Caching.** Long-running tools (AF3, literature search) are memoised on \((p^\star,\mathrm{tool})\) keys; cache TTL configurable.
- **Concurrency.** Tools are marked `read_only` and `concurrency_safe` so nanobot can issue them in parallel.
- **Error envelope.** Uniform `{status, value | reason, latency_ms}`.

---

## 6 Implementation on nanobot

### 6.1 Mapping to nanobot Primitives

| Concern | nanobot construct |
|---------|-------------------|
| LLM provider & routing | `nanobot/providers`; configured in `~/.nanobot/config.json`. |
| Product control flow | CLI `nanobot-bio agent\|chat` → `Nanobot.from_config().run` / `run_streamed` (primary). SDK sketch below is secondary. |
| Bioinformatics tools | Subclasses of `nanobot.agent.tools.base.Tool` under `nanobot/agent/tools/rbp/`; science via App delivery bridge (subprocess). |
| Domain knowledge / prompts | Skill SoT `nanobot/skills/rbp-agent/SKILL.md` (+ optional `references/`); synced into workspace. |
| Tracing for self-evolution | `rbp_eval.nanobot_hooks.RBPTraceHook` → JSONL under `artifacts/traces/`. |
| Hyperparameters | `config/defaults.yaml` (Table 3); offline promote to `config/evolved.yaml`. |
| Caching / memory | Per-tool memoisation; nanobot `session.manager` for conversation continuity. |

### 6.2 Repository Layout

```text
nanobot-bio/
  app/                         # product CLI, backends bridge, integrate, dev gates
  nanobot/
    skills/rbp-agent/
      SKILL.md                 # SoT playbook (always)
      references/              # progressive disclosure (stages, verdict)
    agent/tools/rbp/           # Toolkit SoT (Tool subclasses)
  workspace/skills/rbp-agent/  # sync copy only (do not hand-edit)
  config/                      # defaults.yaml + evolved*.yaml
  rbp_eval/                    # offline Validation Evaluator
  artifacts/{traces,reports,sessions,cache}/
  tests/
```

### 6.3 End-to-End SDK Sketch

Primary UX: `nanobot-bio chat` / `nanobot-bio agent --message "..."`.

```python
from nanobot import Nanobot
from rbp_eval.nanobot_hooks import RBPTraceHook

bot = Nanobot.from_config(
    config_path="~/.nanobot/config.json",
    workspace="/path/to/nanobot-bio/workspace",
)
result = await bot.run(
    "Does this RNA interact with RBP AATF? "
    "RNA: AUGGCU... ; target_uniprot: Q9NY61",
    session_key="rbp:Q9NY61",
    hooks=[RBPTraceHook(out_path="artifacts/traces/run.jsonl")],
)
print(result.content)  # the JSON verdict
```

---

## 7 Self-Evolving Mechanism

The agent improves between deployments through an offline loop driven by a held-out validation set \(\mathcal{D}_{\mathrm{val}}\) of triples \((r,p^\star,y^\star)\), where \(y^\star\in\{0,1\}\) is the ground-truth interaction label.

1. **Trace logging.** Every per-query run writes a structured trace via `RBPTraceHook` (tool calls, returns, fused similarities, final verdict).
2. **Tool attribution.** For each correctly resolved query, the fraction of supporting evidence each tool contributed is recovered from the LLM’s `supporting_rbps` field; tools with persistently low attribution become candidates for retirement.
3. **Weight & threshold re-tuning.** The view-fusion priors and label thresholds are re-fit by minimising a calibrated cross-entropy on \(\mathcal{D}_{\mathrm{val}}\).
4. **Toolkit expansion.** On systematic failure modes (clustered by query embedding), the agent proposes new tools to add (e.g. RNAcompete-derived motifs, protein–protein interaction networks); humans review and merge.
5. **Cache promotion.** Frequently hit \((p^\star\to\{p_i\})\) proxy mappings are promoted to a fast cache, bypassing Stage 1 on subsequent queries.

---

## 8 Default Design Decisions

For the points left open in the initial sketch, we adopt the following defaults to keep the first implementation tractable. Each can be revisited once the self-evolution loop produces evidence.

| Question | Default | Rationale |
|----------|---------|-----------|
| Number of candidates \(N_{\mathrm{cand}}\) | Fixed cap of 5; LLM may drop entries below similarity floor \(\tau_{\mathrm{drop}}=0.30\). | Five proxies are enough to smooth single-model noise without inflating predictor cost; a hard floor avoids spurious low-quality proxies dragging the mean. |
| Fast-path threshold | Strict UniProt match; or sequence identity ≥ 95% flagged as “near-known”. | Strict ID is unambiguous; the 95% near-match rule is a well-established homology cutoff and is reported in the explanation for transparency. |
| Structure data source | Prefer AFDB cache for \(\mathcal{K}\); Foldseek similarity; AF3 optional (`axes.use_af3=false` until probe green); structure failure ≠ sim `0`. | Matches Delivery HANDOFF; avoids AF3 cold-start cost on the catalogue. |
| Output granularity | Four-level label plus **raw** \(\hat{p}\) and rule-based `confidence`. | Aligns with wet-lab triage; does not claim ECE-calibrated P(bind) without reports. |
| Donor aggregation | Default `max` over donor probs; weighted vote available as integrate tool / evolve candidate. | Stable MVP; weighted mean revisitable under offline evolve-eval. |
| Agent framework | nanobot (Python SDK + custom Tool subclasses + a dedicated skill). | Per the team’s existing toolchain; lightweight core, native MCP, and observable via hooks. |

**Table 3:** Default decisions for the open design points.

---

## 9 Evaluation Plan

- **Held-out RBP split.** Partition \(\mathcal{K}\) into seen (training) and held-out (evaluation only) RBPs to simulate the unseen-RBP setting honestly.
- **Primary metrics.** AUROC and AUPRC over the four-level label collapsed to binary; expected calibration error (ECE) on \(\hat{p}\).
- **Ablations.** (i) Single-view retrieval (sequence only / structure only / function only), (ii) fixed-weight average vs. LLM-fused similarity, (iii) Stage 3 LLM explanation removed (numeric aggregation only), (iv) varying \(N_{\mathrm{cand}}\in\{1,3,5,10\}\).
- **Qualitative.** Sample 30 explanations and manually rate faithfulness against the underlying tool outputs.

---

## 10 Milestones

| Wk | Milestone | Owner |
|----|-----------|-------|
| 1 | Lock tool interface schemas (§5) | Both |
| 2 | Implement P0 tools + register with nanobot | Tools owner |
| 2 | Author rbp-agent skill + system prompt; SDK-level smoke test | Agent owner |
| 3 | Implement P1 tools; integrate Stage 1 fusion | Tools owner |
| 3 | Implement RBPTraceHook and trace store | Agent owner |
| 4 | First end-to-end run on a small validation slice; ablation harness | Both |
| 5 | Calibrate thresholds, run full evaluation | Both |
| 6 | Self-evolution loop v1: weight re-tuning on \(\mathcal{D}_{\mathrm{val}}\) | Both |

---

## 11 Open Risks

- **Predictor extrapolation.** If the catalogue is not representative of the held-out RBPs, even the best proxy will be uninformative. Mitigation: report low confidence loudly; surface this in the explanation.
- **LLM hallucinated similarity.** The fused similarity is partly model-generated; we mitigate by exposing the per-view breakdown and by spot-checking with an automated faithfulness probe (Stage 3 evaluation).
- **AF3 cost / availability.** Mitigated by structure caching for \(\mathcal{K}\) and graceful sequence-only fallback for the target.

---

*End of proposal.*
