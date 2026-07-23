# -*- coding: utf-8 -*-
"""10-round chat-equivalent science battery (same stack as ``nanobot-bio chat``).

Covers Stage 0–3 tools + offline/attribution surfaces for the offline evolve loop.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _rna(name: str) -> str:
    from app.backends.delivery.examples import load_example

    return load_example(name)["rna"]


def build_questions() -> list[dict]:
    pos = _rna("pos")
    neg = _rna("neg")
    au = "AUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUA"
    cu = "CUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCU"
    return [
        {
            "id": 1,
            "tag": "stage0_own_head",
            "covers": ["resolve_rbp", "predict_interaction", "trace"],
            "q": (
                f"Does this RNA interact with RBP PTBP1 (UniProt P26599) in cohort K562?\n"
                f"RNA: {pos}\n"
                "Use own-head fast path only."
            ),
        },
        {
            "id": 2,
            "tag": "stage0_neg_control",
            "covers": ["predict_interaction", "label_thresholds"],
            "q": (
                f"Does this RNA interact with RBP PTBP1 in cohort K562?\n"
                f"RNA: {neg}\n"
                "Own-head path; report calibrated label from p_hat."
            ),
        },
        {
            "id": 3,
            "tag": "unseen_multi_view",
            "covers": [
                "seq_similarity",
                "rna_blastn",
                "rna_similarity",
                "domain_architecture",
                "get_func_annotation",
                "fuse_similarity_views",
                "predict_interaction",
            ],
            "q": (
                f"Does this RNA interact with RBP FUS (UniProt P35637) in cohort K562?\n"
                f"RNA: {au}\n"
                "Unseen/near-known path: retrieve multi-view (prefer rna_blastn; "
                "also rna_similarity and state backend=mock or backend=real), "
                "get_func_annotation once, fuse donors ≤5, donor predict, Stage-3 integrate. "
                "Fill supporting_rbps with donor aliases and similarity scores for attribution."
            ),
        },
        {
            "id": 4,
            "tag": "structure_afdb",
            "covers": ["structure_fetch", "struct_similarity", "structure_consensus"],
            "q": (
                f"Does this RNA interact with RBP ELAVL1 (UniProt Q15717) in cohort K562?\n"
                f"RNA: {au}\n"
                "Emphasize structure axis: structure_fetch (AFDB) → struct_similarity "
                "(US-align refine) → optional structure_consensus. Do not invent sim=0 on miss."
            ),
        },
        {
            "id": 5,
            "tag": "function_pdb_literature",
            "covers": ["get_func_annotation", "pdb_metadata", "literature_search"],
            "q": (
                f"Does this RNA interact with RBP QKI (UniProt Q96PU8) in cohort K562?\n"
                f"RNA: ACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACA\n"
                "Call get_func_annotation (pdb_metadata enrichment OK) and ≤1 literature_search "
                "with a precise CLIP/eCLIP query before Checkpoint 1."
            ),
        },
        {
            "id": 6,
            "tag": "rna_fm_axis",
            "covers": ["rna_similarity", "rna_blastn", "backend_label"],
            "q": (
                f"Does this RNA interact with RBP HNRNPC (UniProt P07910) in cohort K562?\n"
                f"RNA: {cu}\n"
                "Require both rna_blastn (if peaks DB) and rna_similarity. "
                "In explanation explicitly say RNA backend mock vs real — never claim RNA-FM if mock."
            ),
        },
        {
            "id": 7,
            "tag": "proxy_cache_hit",
            "covers": ["lookup_proxy_cache", "stage1_bypass"],
            "q": (
                f"Does this RNA interact with RBP FUS (UniProt P35637) in cohort K562?\n"
                f"RNA: {au}\n"
                "Start with lookup_proxy_cache. If hit, skip Stage-1 retrieve and go to donor predict. "
                "This exercises cache promotion / Stage-1 bypass for the offline evolve loop."
            ),
        },
        {
            "id": 8,
            "tag": "transfer_priors_stage3",
            "covers": [
                "transfer_prior_lookup",
                "donor_quality_prior",
                "similarity_weighted_vote",
                "confidence_abstain",
            ],
            "q": (
                f"Does this RNA interact with RBP DROSHA (UniProt Q9NRR4) in cohort K562?\n"
                f"RNA: {pos}\n"
                "Unseen path: fuse → confidence_abstain → predict donors, then Stage-3 "
                "transfer_prior_lookup, donor_quality_prior, similarity_weighted_vote, "
                "then JSON verdict. supporting_rbps must list tools/donors contributing evidence."
            ),
        },
        {
            "id": 9,
            "tag": "ood_low_confidence",
            "covers": ["checklist", "confidence_low", "abstain"],
            "q": (
                "Does this RNA interact with a hypothetical dark RBP "
                "'Xenopus_FakeRBP_99' (no UniProt) in cohort K562?\n"
                f"RNA: GCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGC\n"
                "Expect missing prior / weak structure / sparse retrieval → force confidence low "
                "or abstain; p_hat only from tools (null OK). Do not invent scores."
            ),
        },
        {
            "id": 10,
            "tag": "evolve_surface_attribution",
            "covers": ["supporting_rbps", "fuse_similarity_views", "trace_logging"],
            "q": (
                f"Does this RNA interact with RBP CPSF6 (UniProt Q16630) in cohort K562?\n"
                f"RNA: {pos}\n"
                "Full retrieve→predict→integrate. In supporting_rbps, for each donor include "
                "alias, prob, similarity_score, and which view dominated (esmc/domain/struct/rna). "
                "This mirrors offline tool-attribution from traces for weight retune on Dval."
            ),
        },
    ]


def main() -> int:
    os.environ.setdefault("NANOBOT_BIO_ROOT", str(ROOT))
    # Science env (caller should also export RNA_FM_*)
    from app.core.paths import REPORTS, TRACES, ensure_artifact_dirs
    from app.dotenv_util import load_dotenv

    try:
        load_dotenv()
    except Exception:
        pass

    ensure_artifact_dirs()
    from app.integrate import RBPAgent
    from app.core.chat_ux import run_agent_turn_streamed_sync, ensure_bio_branding
    from nanobot.agent.tools.rbp.annotation import reset_tool_turn_guards

    try:
        from rbp_eval.nanobot_hooks import RBPTraceHook
    except ImportError:
        from rbp_eval.hooks import JsonlTraceHook as RBPTraceHook

    session_key = f"chat-battery-{int(time.time())}"
    trace_path = TRACES / f"{session_key}.jsonl"
    hook = RBPTraceHook(trace_path)
    agent = RBPAgent(
        offline=False,
        device="auto",
        use_conda=True,
        prefer_nanobot_llm=True,
        allow_fallback=False,
        hooks=[hook],
    )
    bot_name, bot_icon = ensure_bio_branding()
    questions = build_questions()
    rows: list[dict] = []

    print(f"=== 10-round chat battery · session={session_key} ===")
    print(f"trace={trace_path}")
    print(f"tools={len(agent.tool_names)}")

    for item in questions:
        reset_tool_turn_guards()
        prompt = (
            item["q"]
            + "\n\n[Output contract] Reply with ONE raw JSON object only "
            "(no markdown fences). Fields: label, p_hat, confidence, explanation, "
            "supporting_rbps. p_hat only from predict tools."
        )
        print(f"\n----- Round {item['id']}/10 [{item['tag']}] -----", flush=True)
        t0 = time.perf_counter()
        try:
            result = run_agent_turn_streamed_sync(
                agent,
                prompt,
                session_key=session_key,
                extra_hooks=[],
                bot_name=bot_name,
                bot_icon=bot_icon,
            )
            dt = round((time.perf_counter() - t0) * 1000.0, 1)
            v = result.verdict if isinstance(result.verdict, dict) else {}
            row = {
                "id": item["id"],
                "tag": item["tag"],
                "covers": item["covers"],
                "ok": result.mode == "nanobot_llm" and not result.error,
                "mode": result.mode,
                "tools_used": list(result.tools_used or []),
                "label": v.get("label"),
                "p_hat": v.get("p_hat"),
                "confidence": v.get("confidence"),
                "n_supporting": len(v.get("supporting_rbps") or []),
                "latency_ms": dt,
                "error": result.error,
                "explanation_len": len(str(v.get("explanation") or "")),
            }
        except Exception as e:
            row = {
                "id": item["id"],
                "tag": item["tag"],
                "covers": item["covers"],
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            }
        rows.append(row)
        print(
            json.dumps(
                {k: row[k] for k in ("id", "tag", "ok", "mode", "label", "p_hat", "tools_used") if k in row},
                ensure_ascii=False,
            ),
            flush=True,
        )

    report = {
        "schema": "chat_ten_round_battery.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_key": session_key,
        "trace": str(trace_path),
        "n_ok": sum(1 for r in rows if r.get("ok")),
        "n_total": len(rows),
        "rows": rows,
        "evolve_loop_mapping": {
            "trace_logging": str(trace_path),
            "tool_attribution": "supporting_rbps in verdicts (rounds 3,8,10)",
            "weight_retune": "offline: nanobot-bio evolve / evolve-eval on Dval",
            "toolkit_expansion": "human review; not auto-merged this battery",
            "cache_promotion": "lookup_proxy_cache round 7",
        },
        "ok": sum(1 for r in rows if r.get("ok")) >= 8,
    }
    out = REPORTS / "chat_ten_round_battery.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = REPORTS / "chat_ten_round_battery.md"
    lines = [
        "# 10-round chat science battery",
        "",
        f"- session: `{session_key}`",
        f"- ok: {report['n_ok']}/{report['n_total']}",
        f"- trace: `{trace_path}`",
        "",
        "| # | tag | ok | label | p_hat | tools |",
        "|---|-----|----|-------|-------|-------|",
    ]
    for r in rows:
        tools = ",".join((r.get("tools_used") or [])[:6])
        lines.append(
            f"| {r.get('id')} | {r.get('tag')} | {r.get('ok')} | {r.get('label')} | "
            f"{r.get('p_hat')} | {tools} |"
        )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport: {out}")
    print(f"md: {md}")
    print(json.dumps({"n_ok": report["n_ok"], "n_total": report["n_total"], "ok": report["ok"]}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
