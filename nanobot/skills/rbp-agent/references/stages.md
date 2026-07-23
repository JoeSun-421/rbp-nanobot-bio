# Stage playbooks (detail)

> Loaded on demand. Hard rules + decision tree stay in SKILL.md.

## 4. Stage 0 — Own-head (in-catalogue)

**Goal:** If the target RBP has its own RhoBind head, use that head **once** and stop.

### Steps

1. Parse the user message → extract **RNA sequence** + **target RBP** (name / UniProt / alias).  
   If RNA is missing → ask **once**, then wait.
2. Call `resolve_rbp` (fallback: `get_known_rbp_list` with a `query`).
3. If `in_panel=true`:
   - Call `predict_interaction(rna, rbp_id=<alias>, cohort)` **exactly once**
   - `p_hat` = `predictions[0].prob`
   - `supporting_rbps` = `[{ "alias", "rbp_id": <uniprot>, "prob": p_hat, "similarity_score": 1.0 }]`
   - `explanation` must state **own-head / in-catalogue** (include `cohort` / `head_index` when tools provide them)
   - Emit final JSON and **STOP**

### Stage 0 forbids

After a successful in-panel resolve, do **not** call:

`seq_similarity`, `rna_similarity`, `rna_blastn`, `domain_architecture`, `struct_*`, `structure_*`, `literature_search`, `fuse_*`, `similarity_weighted_vote`, transfer / abstain tools.

### Near-known Fast Path (in_panel=false)

1. Call `check_near_known` (MMseqs identity vs catalogue; threshold **0.95**).
2. If `near_match=true` and `donor_alias` has a head:
   - `predict_interaction(rna, rbp_id=<donor_alias>)` **once**
   - Set `near_match=true` in verdict extras / explanation; emit JSON and **STOP**
3. Else continue Stage 1 (unseen).

---

## 5. Stage 1 — Retrieve (unseen / cache miss)

**Goal:** Find up to **5** donor RBPs that have heads, via multi-view similarity.

**Canonical order (BUILD_SPEC):** characterize → **parallel** retrieve → fuse → **`confidence_abstain`** → Stage 2 predict.

### 5.1 Cache first

Call `lookup_proxy_cache`.

| Result | Action |
| --- | --- |
| **Hit** | Skip multi-view retrieve; still run **`confidence_abstain`** on embedding-like hits before Stage 2 |
| **Miss** | Continue §5.2 |

### 5.2 Characterize (before parallel retrieve)

| Tool | Role |
| --- | --- |
| `structure_fetch` | AFDB / cache for the query RBP |
| `get_func_annotation` | Function / GO / **function_category** / optional pdb_metadata (**≤ 1** / UniProt) — Checkpoint 1 input |
| `domain_architecture` | Domains / RBD ranges (feed `predict_structure(regions=…)` later if AF3 needed) |

### 5.3 Parallel multi-view retrieve (`parallel_retrieve=true`)

Run **in parallel intent** (batch tool calls in one turn when possible):

| Tool | Axis | Notes |
| --- | --- | --- |
| `seq_similarity` | `hits_emb` + `hits_seq` | Default dual-axis (ESM-C + MMseqs). Prefer `alias`/`uniprot`. **Never** pass RNA. |
| `rna_blastn` | RNA peaks | Prefer when peaks DB available; cite as `rna_blastn` (**not** RNA-FM) |
| `rna_similarity` | RNA embed | Report `backend=mock\|real`; mock ≠ “used RNA-FM” |
| `struct_similarity` | Structure | After `structure_fetch`; US-align refine default-on |
| `structure_consensus` | Structure | When multiple PDBs |
| `literature_search` | Function context | Unseen: **≤ 1** precise CLIP/eCLIP query |

Raw delivery tools (`esm_embed`, `colabfold_msa`, `pymol_util`, `function_category`, …) are registered when useful — prefer curated wrappers above.

### 5.4 Fuse donors (deterministic baseline)

```text
fuse_similarity_views(
  hits_emb=..., hits_seq=..., hits_struct=..., hits_dom=...,
  exclude_aliases=[target]
)
# or hit_lists=[hits_emb, hits_seq, ...]
```

**Fusion rules**

| Rule | Value |
| --- | --- |
| Include RNA view when available | `rna_embed` / `rna_fm` from `rna_similarity` |
| `rna_blastn` | Separate evidence — **do not** rename to RNA-FM |
| Claim “RNA-FM”? | Only if `backend=real` |
| Drop donors | Fused similarity **&lt; 0.30** (`τ_drop`) |
| Cap | **N_cand ≤ 5** |
| Checkpoint 1 | Confirm/trim fused donors using function text — **do not invent scores** |

### 5.5 Abstain **before** predict (mandatory on transfer)

```text
confidence_abstain(hits=<hits_emb or fused embedding hits>)
```

- Use **embedding** hits (`hits_emb`) when available.
- If `confident=false` → hedge / low confidence; you may still predict donors but must surface abstain in `caveats`.
- Runtime **blocks** `predict_interaction` on transfer/multi-donor until `confidence_abstain` has been called this turn.

### 5.6 Structure axis order

1. `structure_fetch` (AFDB / cache)
2. `struct_similarity` (Foldseek; US-align refine when enabled)
3. Optional `structure_consensus`
4. Else `predict_structure` (AF3) **≤ 1** — pass `regions=[[start,end],…]` from domain/RBD when known
5. Else `structure_axis=unavailable` → continue without structure zeros; force **low confidence**

**Critical:** structure failure is **not** similarity `0`. Omit that axis.

### 5.7 Sequence failure fallback

If ESM fails but MMseqs returned `hits_seq`, continue with seq axis only and keep confidence low.

---

## 6. Stage 2 — Predict donors

**Goal:** Score the query RNA under each donor’s RhoBind head (**after** §5.5 abstain).

```text
predict_interaction(rna, rbps=[donor aliases…])   # batch preferred
```

| Situation | Action |
| --- | --- |
| Single donor fails inside a batch | Skip that donor; do **not** blindly retry the whole batch |
| Collect scores | Only `prob` from successful tool rows |
| Batch / head fails with OOM or timeout | **No retry** → `p_hat: null`, low confidence |

---

## 7. Stage 3 — Integrate + evidence critic

**Goal:** Turn donor probabilities + similarities into one grounded verdict.

### 7.1 Tool order

Call in order (skip only if required inputs are missing):

| # | Tool | Purpose |
| --- | --- | --- |
| 1 | `transfer_prior_lookup` | LOO / transfer prior for the method |
| 2 | `donor_quality_prior` | Down-weight weak donors |
| 3 | `similarity_weighted_vote` | Fuse probs × similarities |
| 4 | *(no tool)* Evidence critic | Checklist below → may force low confidence |

> Note: `confidence_abstain` is **Stage 1.5** (post-fuse, pre-predict), not Stage 3.

### 7.2 `similarity_weighted_vote` input shape

```json
[{"donor": "PTBP1", "prob": 0.96}]
```

**Not** `{"PTBP1": 0.96}`. Hits must carry real similarity scores from Stage 1 / fusion.

### 7.3 Evidence checklist

Mark each row **pass** or **fail**. State the count in `explanation` (e.g. `checklist failures=2`).

| # | Item | Fail when |
| --- | --- | --- |
| 1 | Structure axis | `structure_axis=unavailable`, or AF3/AFDB missing / `structure_trust!=ok` |
| 2 | Domain / RBD | `domain_architecture` empty **and** donors lack shared RBD-type evidence |
| 3 | Kingdom / panel match | Cross-kingdom or clearly non-RBP query vs human CLIP-trained donors |
| 4 | LOO prior | `prior_missing=true` or no transfer prior for target |
| 5 | RNA axis | Query RNA present but RNA view missing/failed → `rna_axis=unavailable` |

**Hard rules**

- If **≥ 2** items fail → force low confidence even when `p_hat` is large.
- High ESM similarity with function/domain mismatch (shared fold ≠ RNA binding) counts as an **extra** failure under item 2 or 3.
- `confidence_abstain` does **not** override this. Runtime `normalize_verdict` also enforces checklist ≥ 2 → low confidence.

### 7.4 Missing LOO prior (common for novel UniProt)

- Set `prior_missing=true` in reasoning / explanation
- Force low confidence
- Explain: LOO calibrates the **method** on held-out catalogue RBPs — it does **not** supply a per-target prior
- Never silently ignore a missing prior

### 7.5 Scientific caveat (always when transferring)

Transfer / “dark protein” scores are **cautious triage only** — **not** a substitute for CLIP / eCLIP wet-lab evidence. Say this in `explanation`.

If integrate tools fail: fall back to a weighted average of **tool-returned numbers only**. Still emit JSON; `p_hat` remains tool-sourced (or `null`).

---

