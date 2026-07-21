#!/usr/bin/env python3
"""RNA–RBP agent CLI.

Product path is always ``Nanobot.run`` (true agent) with the delivery tools
registered. ``onboard`` writes the LLM provider + key + model.

Usage::

  rbp-agent doctor
  rbp-agent onboard        # pick provider, enter API key + model
  rbp-agent agent --message "Does this RNA interact with RBP …?"
  rbp-agent chat           # multi-turn agent loop
  rbp-agent mvp
"""

from __future__ import annotations

import argparse
import json
import os
import time
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]  # nanobot-bio repo root

# Load setup_all-generated .env (do not override explicit exports)
try:
    from rbp_agent.dotenv_util import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except Exception:
    pass

BIO_ROOT = Path(os.environ.get("BIO_ROOT", ROOT.parent)).expanduser().resolve()
os.environ.setdefault("BIO_ROOT", str(BIO_ROOT))
os.environ.setdefault("NANOBOT_BIO_ROOT", str(ROOT))
os.environ.setdefault("NANOBOT_SRC", str(BIO_ROOT / "nanobot"))

# Sibling nanobot runtime first, then agent package
_br = str(BIO_ROOT)
_rt = str(ROOT)
for _p in (_br, _rt):
    while _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, _br)
sys.path.insert(1, _rt)


def _read_fasta(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "".join(ln.strip() for ln in lines if ln.strip() and not ln.startswith(">"))


def cmd_doctor(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from rbp_agent.backends.delivery.client import DeliveryToolClient, SCRIPT_MAP, tools_meta_by_name
    from rbp_agent.backends.delivery.env import apply_delivery_env, resolve_delivery_paths
    from rbp_agent.core.chat_ux import cgroup_memory_gb, memory_blocker_message
    from rbp_agent.core.paths import ARTIFACTS, REPORTS, ensure_artifact_dirs

    apply_delivery_env()
    sync_ok = False
    sync_err = None
    try:
        from rbp_agent.sync_overlay import sync_overlay

        sync_ok = sync_overlay(quiet=True) == 0
    except Exception as e:
        sync_err = f"{type(e).__name__}: {e}"
    dirs = ensure_artifact_dirs()
    paths = resolve_delivery_paths()
    print("=== rbp-agent doctor ===")
    print(f"DELIVERY_ROOT={paths['delivery_root']}")
    path_status: dict[str, dict[str, object]] = {}
    for k in ("rbp_registry", "predict_api", "registry_json", "agent_db", "rhobind_release"):
        p = paths[k]
        ok = p.exists()
        path_status[k] = {"ok": ok, "path": str(p)}
        print(f"  {k}: {'OK' if ok else 'MISSING'}  {p}")

    print(f"artifacts root: {ARTIFACTS}")
    for name, p in dirs.items():
        print(f"  {name}: {'OK' if p.exists() else 'MISSING'}  {p}")

    meta = tools_meta_by_name()
    print(f"delivery registry tools: {len(meta)}")
    missing = [n for n in SCRIPT_MAP if not (paths["delivery_root"] / SCRIPT_MAP[n]).is_file()]
    print(f"SCRIPT_MAP: {len(SCRIPT_MAP)}  missing: {len(missing)}")

    gb = cgroup_memory_gb()
    print(f"cgroup memory.max: {'unlimited' if gb is None else f'{gb:.2f} GiB'}")
    mem_warn = memory_blocker_message()
    if mem_warn:
        print(mem_warn)

    print(f"HF_HOME={os.environ.get('HF_HOME') or '(unset)'}")
    print(f"HF_ENDPOINT={os.environ.get('HF_ENDPOINT') or '(unset — optional mirror e.g. https://hf-mirror.com)'}")
    print(f"OMP_NUM_THREADS={os.environ.get('OMP_NUM_THREADS') or '(unset)'}")

    rhobind_py = None
    protein_embed_py = None
    try:
        from rbp_agent.backends.delivery.client import DeliveryToolClient as _DTC

        for env_name, slot in (("rhobind", "rhobind"), ("protein_embed", "embed")):
            pref = _DTC._conda_env_prefix(env_name)
            if pref is not None:
                cand = pref / "bin" / "python"
                if cand.is_file():
                    if slot == "rhobind":
                        rhobind_py = cand
                    else:
                        protein_embed_py = cand
    except Exception:
        pass
    print(
        f"rhobind python: {'OK' if rhobind_py else 'MISSING'}  "
        f"{rhobind_py or '(install via delivery setup_envs.sh)'}"
    )
    print(
        f"protein_embed python: {'OK' if protein_embed_py else 'MISSING'}  "
        f"{protein_embed_py or '(needed for ESM-C seq_similarity)'}"
    )

    cli = DeliveryToolClient(offline=True, device="cpu", use_conda=False)
    r = cli.call("resolve_rbp", {"query": "PTBP1"})
    print(f"resolve_rbp(PTBP1): matched={r.get('matched')} alias={r.get('alias')}")
    print(
        f"Stage-0 ready: in_panel={r.get('in_panel')} "
        f"head_index={r.get('head_index')}"
    )
    golden_ok = False
    golden_detail = ""
    try:
        from rbp_agent.backends.delivery.examples import load_example

        ex = load_example("pos")
        golden_ok = True
        golden_detail = f"rna_len={len(ex['rna'])} path={ex['rna_path']}"
        print(f"golden example pos: {golden_detail}")
    except Exception as e:
        golden_detail = str(e)
        print(f"golden example pos: MISSING ({e})")

    skill = ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md"
    skill_ok = skill.is_file() and "always: true" in skill.read_text(encoding="utf-8")
    print(f"SKILL always-on: {'OK' if skill_ok else 'FAIL'}")

    matrix_path = None
    try:
        from rbp_agent.core.model_registry import write_capability_matrix

        matrix_path = write_capability_matrix()
        print(f"model capability matrix: {matrix_path}")
    except Exception as e:
        print(f"model capability matrix: FAIL ({type(e).__name__}: {e})")

    # Real ESM probe (not just import) — needs AA sequence; cgroup OOM → FAIL+hint
    esm_ok = False
    esm_detail = ""
    try:
        from nanobot.agent.tools.rbp.common import load_catalogue_sequence

        seq = load_catalogue_sequence("PTBP1") or ""
        esm_cli = DeliveryToolClient(offline=True, device="cpu", use_conda=True)
        if not seq:
            esm_detail = "no catalogue sequence for PTBP1"
        else:
            esm = esm_cli.call(
                "esm_similarity",
                {
                    "sequence": seq,
                    "encoder": "esmc",
                    "device": "cpu",
                    "top_k": 3,
                },
            )
            hits = esm.get("hits") or []
            err_s = str(esm.get("error") or "")
            if hits and not esm.get("error"):
                esm_ok = True
                top = hits[0]
                esm_detail = (
                    f"top={top.get('alias')} score={top.get('score')} "
                    f"n_hits={len(hits)}"
                )
            elif "rc=-9" in err_s or "Killed" in err_s:
                esm_detail = (
                    "killed/OOM (rc=-9) — raise cgroup memory for protein_embed; "
                    + err_s[:160]
                )
            else:
                esm_detail = (err_s or "no hits")[:240]
    except Exception as e:
        esm_detail = f"{type(e).__name__}: {e}"[:240]
    print(f"ESM probe (PTBP1): {'OK' if esm_ok else 'FAIL'}  {esm_detail}")
    if not esm_ok:
        print(
            "  hint: set HF_HOME to local weights dir; optional HF_ENDPOINT=https://hf-mirror.com; "
            "ensure protein_embed conda env; OMP_NUM_THREADS=1..8; ≥8 GiB RAM for ESM"
        )

    ok_bridge = bool(r.get("matched") and r.get("in_panel") and skill_ok)
    status = "FAIL"
    rc = 1
    if ok_bridge and (mem_warn or not esm_ok):
        status = "WARN"
        rc = 0
        print(
            "doctor: WARN (Stage-0 wiring OK; "
            + ("RhoBind may OOM; " if mem_warn else "")
            + ("ESM not usable — transfer quality will drop" if not esm_ok else "")
            + ")"
        )
    elif ok_bridge:
        status = "OK"
        rc = 0
        print("doctor: OK")
    else:
        print("doctor: FAIL")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "sync_overlay_ok": sync_ok,
        "sync_overlay_error": sync_err,
        "delivery_root": str(paths["delivery_root"]),
        "paths": path_status,
        "script_map": {"total": len(SCRIPT_MAP), "missing": len(missing), "missing_names": missing[:20]},
        "registry_tools": len(meta),
        "cgroup_memory_gib": gb,
        "memory_warn": bool(mem_warn),
        "rhobind_python": str(rhobind_py) if rhobind_py else None,
        "protein_embed_python": str(protein_embed_py) if protein_embed_py else None,
        "resolve_rbp": {
            "matched": r.get("matched"),
            "alias": r.get("alias"),
            "in_panel": r.get("in_panel"),
            "head_index": r.get("head_index"),
        },
        "golden_example_pos": {"ok": golden_ok, "detail": golden_detail},
        "skill_always_on": skill_ok,
        "esm_probe": {"ok": esm_ok, "detail": esm_detail},
        "hf_home": os.environ.get("HF_HOME"),
        "hf_endpoint": os.environ.get("HF_ENDPOINT"),
    }
    out = REPORTS / "doctor_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"doctor report: {out}")
    return rc


def cmd_gate(args: argparse.Namespace) -> int:
    from rbp_agent.acceptance.gate import run_gate

    return int(
        run_gate(
            skip_eval=bool(getattr(args, "skip_eval", False)),
            with_cov=not bool(getattr(args, "no_cov", False)),
        )
    )

def cmd_onboard(args: argparse.Namespace) -> int:
    """Configure LLM provider + API key + model (writes nanobot config)."""
    from rbp_agent.core.onboard import (
        current_summary,
        interactive_onboard,
        list_models_text,
        save_provider,
        DEFAULT_CONFIG,
    )

    if getattr(args, "list_models", False):
        print(list_models_text())
        return 0

    if getattr(args, "show", False):
        print(current_summary())
        return 0

    provider = getattr(args, "provider", None)
    if provider:
        model = getattr(args, "model", None)
        if not model:
            print("--model is required with --provider", file=sys.stderr)
            print("Tip: rbp-agent onboard --list-models", file=sys.stderr)
            return 2
        save_provider(
            provider=provider,
            model=model,
            api_key=getattr(args, "key", None),
            api_base=getattr(args, "api_base", None),
        )
        print(f"saved → {DEFAULT_CONFIG}  [{provider} · {model}]")
        return 0

    return 0 if interactive_onboard() else 1


def cmd_mvp(args: argparse.Namespace) -> int:
    from rbp_agent.acceptance.mvp import main as mvp_main

    return int(mvp_main())


def cmd_own_head(args: argparse.Namespace) -> int:
    """Ideal-env scientific accept: delivery own-head on sample_rna_pos (no LLM)."""
    from rbp_agent.acceptance.own_head import main as own_main

    return int(own_main())


def cmd_eval_plan(args: argparse.Namespace) -> int:
    """Evaluation plan: held-out LOO + ablations + metrics report."""
    from rbp_eval.evaluation_plan import main as eval_main

    argv: list[str] = []
    if getattr(args, "with_seq", False):
        argv.append("--with-seq")
    if getattr(args, "labels", None):
        argv.extend(["--labels", str(args.labels)])
    if getattr(args, "out", None):
        argv.extend(["--out", str(args.out)])
    return int(eval_main(argv))


def cmd_evolve(args: argparse.Namespace) -> int:
    """Offline self-evolution: LOO val batch → attribution / retune / cache / report."""
    from rbp_agent.core.paths import (
        DEFAULT_EVAL_TRACE,
        DEFAULT_EVOLVE_REPORT,
        DEFAULT_VAL_BATCH,
        TRACES,
        ensure_artifact_dirs,
    )
    from rbp_eval.evaluator import run_self_evolution, summarize_verdicts
    from rbp_eval.runner import load_traces, run_loo_val_batch

    ensure_artifact_dirs()
    top_k = int(getattr(args, "top_k", 5) or 5)
    trace_path = Path(getattr(args, "trace", None) or DEFAULT_EVAL_TRACE)
    out_json = Path(getattr(args, "out", None) or DEFAULT_VAL_BATCH)
    if not out_json.is_absolute():
        out_json = ROOT / out_json

    results, held_hits = run_loo_val_batch(
        top_k=top_k,
        trace_path=trace_path,
        with_esm=bool(getattr(args, "with_esm", False)),
    )
    summary = summarize_verdicts(results)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(
            {"summary": summary, "n": len(results), "results": results},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("val_batch:", out_json)
    print("summary:", json.dumps(summary, ensure_ascii=False))

    scored_labels: list[dict] | None = None
    labels_path = getattr(args, "with_labels", None)
    if labels_path:
        lp = Path(labels_path)
        if not lp.is_absolute():
            lp = ROOT / lp
        raw = json.loads(lp.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            scored_labels = raw
        elif isinstance(raw, dict) and isinstance(raw.get("scored_labels"), list):
            scored_labels = raw["scored_labels"]
        else:
            print("WARN: --with-labels must be a JSON list of {p_hat,y}", file=sys.stderr)

    traces = load_traces(trace_path)
    # Merge other agent JSONL under artifacts/traces/ (exclude the val trace itself)
    try:
        for p in sorted(TRACES.glob("*.jsonl")):
            if p.resolve() == Path(trace_path).expanduser().resolve():
                continue
            traces.extend(load_traces(p))
    except OSError:
        pass

    report = run_self_evolution(
        results,
        held_to_hit_lists=held_hits,
        scored_labels=scored_labels,
        traces=traces,
        top_k=top_k,
        write_config=True,
    )
    print("self_evolution_report:", DEFAULT_EVOLVE_REPORT)
    print("candidate_config:", report.evolved_config_path)
    print("Promote after gate: rbp-agent promote-evolved")
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False)[:3000])
    return 0


def cmd_evolve_eval(args: argparse.Namespace) -> int:
    """Light nested-split eval: retune on train half, score defaults vs retuned on test."""
    from rbp_eval.evolve_eval import run_evolve_eval

    tier_a = getattr(args, "tier_a_ok", None)
    if tier_a == "true":
        tier_a_ok: bool | None = True
    elif tier_a == "false":
        tier_a_ok = False
    else:
        # Infer from latest gate_report if present
        tier_a_ok = None
        try:
            from rbp_agent.core.paths import REPORTS

            gp = REPORTS / "gate_report.json"
            if gp.is_file():
                tier_a_ok = bool(json.loads(gp.read_text(encoding="utf-8")).get("ok"))
        except Exception:
            tier_a_ok = None

    out = Path(getattr(args, "out", None) or "")
    if not out.parts:
        from rbp_agent.core.paths import REPORTS

        out = REPORTS / "evolve_eval_report.json"
    if not out.is_absolute():
        out = ROOT / out
    md = Path(getattr(args, "md", None) or out.with_suffix(".md"))
    if not md.is_absolute():
        md = ROOT / md

    report = run_evolve_eval(
        seed=int(getattr(args, "seed", 42) or 42),
        n_test=int(getattr(args, "n_test", 5) or 5),
        top_k=int(getattr(args, "top_k", 5) or 5),
        with_esm=bool(getattr(args, "with_esm", False)),
        include_live=not bool(getattr(args, "no_live", False)),
        tier_a_ok=tier_a_ok,
        out_json=out,
        out_md=md,
        write=True,
    )
    print("evolve_eval:", report.get("paths", {}).get("json", out))
    print("delta_auprc:", report.get("delta_auprc"))
    print("promote:", json.dumps(report.get("promote"), ensure_ascii=False))
    return 0


def cmd_promote_evolved(args: argparse.Namespace) -> int:
    """Promote config/evolved.candidate.yaml → evolved.yaml after light eval asserts."""
    from rbp_eval.evaluator import promote_evolved_config

    try:
        path = promote_evolved_config(
            require_reports=not bool(getattr(args, "force", False)),
        )
    except Exception as e:
        print(f"promote-evolved FAIL: {e}", file=sys.stderr)
        return 1
    print(f"promoted → {path}")
    return 0


def cmd_compliance(args: argparse.Namespace) -> int:
    from rbp_agent.acceptance.compliance import main as compliance_main

    return int(compliance_main())


def cmd_layout(args: argparse.Namespace) -> int:
    from rbp_agent.acceptance.layout import main as layout_main

    try:
        layout_main()
    except SystemExit as e:
        return int(e.code or 0)
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """One-shot Nanobot.run (primary agent path). No pipeline fallback."""
    from rbp_agent.core.chat_ux import (
        configure_chat_logging,
        format_verdict_display,
        memory_blocker_message,
        print_banner,
        print_registration,
        print_verdict_block,
        run_agent_turn_streamed_sync,
    )
    from rbp_agent.integrate import skill_path as _skill_path

    configure_chat_logging(verbose=bool(getattr(args, "verbose", False)))
    print_banner(subtitle="one-shot agent · thinking + tools visible")
    warn = memory_blocker_message()
    if warn:
        print(warn, file=sys.stderr)

    try:
        from rbp_agent.integrate import RBPAgent
    except ImportError as e:
        print("integrate import failed:", e, file=sys.stderr)
        return 1

    try:
        from rbp_eval.nanobot_hooks import RBPTraceHook
    except ImportError:
        from rbp_eval.hooks import JsonlTraceHook as RBPTraceHook

    if getattr(args, "example", None):
        from rbp_agent.backends.delivery.examples import own_head_prompt

        message = own_head_prompt(args.example)
    elif getattr(args, "message", None):
        message = args.message
    else:
        parts = []
        if args.query:
            parts.append(f"RBP {args.query}")
        if args.uniprot:
            parts.append(f"target_uniprot: {args.uniprot}")
        if args.rna_file:
            raw = Path(args.rna_file).read_text(encoding="utf-8")
            rna = "".join(
                ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.startswith(">")
            )
            parts.append(f"RNA: {rna}")
        if args.sequence_fasta:
            seq = _read_fasta(Path(args.sequence_fasta))
            parts.append(f"protein_sequence: {seq[:80]}... (len={len(seq)})")
            parts.append(f"FULL_SEQ: {seq}")
        if args.force_transfer:
            parts.append(
                "force_transfer: treat target as unseen even if in_panel "
                "(run Stage 1–3; do not use own-head stop)."
            )
        if not parts:
            print(
                "Need --message, --example pos|neg, or --query/--rna-file.\n"
                "Ideal-env own-head smoke:  rbp-agent agent --example pos",
                file=sys.stderr,
            )
            return 2
        message = "Does this RNA interact with the target RBP? " + " ; ".join(parts)

    if getattr(args, "fallback", False) or getattr(args, "offline", False):
        print(
            "ERROR: pipeline fallback removed from product CLI.\n"
            "Use Nanobot agent path only (rbp-agent agent|chat|own-head).",
            file=sys.stderr,
        )
        return 2

    from rbp_agent.core.paths import TRACES, ensure_artifact_dirs

    ensure_artifact_dirs()
    trace = TRACES / "cli_agent.jsonl"
    try:
        from nanobot.agent.tools.rbp.annotation import reset_tool_turn_guards

        reset_tool_turn_guards()
    except Exception:
        pass

    agent = RBPAgent(
        offline=False,
        device=args.device or "auto",
        use_conda=True,
        prefer_nanobot_llm=True,
        allow_fallback=False,
        auto_install_into_nanobot=False,
        hooks=[RBPTraceHook(trace)],
    )
    try:
        agent.get_nanobot()
    except Exception as e:
        print(f"Failed to start: {e}", file=sys.stderr)
        return 1
    print_registration(agent.tool_names, skill_path=_skill_path())

    prompt = (
        message
        + "\n\n[Output contract] Reply with ONE raw JSON object only "
        "(no markdown fences). Fields: label, p_hat, confidence, "
        "explanation, supporting_rbps. "
        "If resolve_rbp.in_panel=true: own-head predict once then STOP. "
        "`p_hat` comes only from predict tools."
    )
    result = run_agent_turn_streamed_sync(
        agent,
        prompt,
        session_key=getattr(args, "session_key", None) or "rbp:cli",
        extra_hooks=[],
    )
    display = format_verdict_display(result)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(display, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print_verdict_block(display)
    if getattr(args, "strict", False) and result.mode != "nanobot_llm":
        return 2
    return 0 if result.mode != "error" else 1

def cmd_chat(args: argparse.Namespace) -> int:
    """Multi-turn agent: quiet logs, visible thinking/tools, JSON verdict."""
    from rbp_agent.core.chat_ux import (
        CHAT_HELP,
        configure_chat_logging,
        format_verdict_display,
        memory_blocker_message,
        print_chat_header,
        print_registration,
        print_status_panel,
        print_turn_footer,
        print_verdict_block,
        read_user_message,
        run_agent_turn_streamed_sync,
    )
    from rbp_agent.integrate import skill_path as _skill_path

    verbose = bool(getattr(args, "verbose", False))
    configure_chat_logging(verbose=verbose)

    try:
        from rbp_agent.integrate import RBPAgent
    except ImportError as e:
        print("Failed to import rbp_agent.integrate:", e, file=sys.stderr)
        return 1
    try:
        from rbp_eval.nanobot_hooks import RBPTraceHook
    except ImportError:
        from rbp_eval.hooks import JsonlTraceHook as RBPTraceHook

    cfg = Path(os.environ.get("NANOBOT_CONFIG", "~/.nanobot/config.json")).expanduser()
    if not cfg.is_file():
        print("No LLM configured. Run:  rbp-agent onboard", file=sys.stderr)
        return 1

    session_key = getattr(args, "session_key", None) or f"chat-{os.getpid()}"
    device = getattr(args, "device", None) or "auto"
    from rbp_agent.core.paths import TRACES, ensure_artifact_dirs

    ensure_artifact_dirs()
    trace = TRACES / "cli_chat.jsonl"

    agent = RBPAgent(
        offline=False,
        device=device,
        use_conda=True,
        prefer_nanobot_llm=True,
        allow_fallback=False,
        auto_install_into_nanobot=False,
        hooks=[RBPTraceHook(trace)],
    )
    try:
        agent.get_nanobot()
    except Exception as e:
        print(f"Failed to start: {e}", file=sys.stderr)
        print("Fix: rbp-agent onboard   (set provider + API key)", file=sys.stderr)
        return 1

    try:
        from rbp_agent.core.onboard import current_summary

        summary = current_summary()
    except Exception:
        summary = "?"

    skill = _skill_path()
    skill_ok = bool(skill and skill.is_file())
    print_chat_header(
        llm_summary=summary,
        n_tools=len(agent.tool_names),
        skill_ok=skill_ok,
        mem_warn=memory_blocker_message(),
        session_key=session_key,
    )
    print_registration(agent.tool_names, skill_path=skill)

    while True:
        msg = read_user_message("❯ ")
        if msg is None:
            print()
            return 0
        msg = msg.strip()
        if not msg:
            continue
        low = msg.lower().split()[0] if msg else ""

        if low in ("/quit", "/exit", "quit", "exit"):
            print("bye.", file=sys.stderr)
            return 0
        if low in ("/help", "/?"):
            print(CHAT_HELP, file=sys.stderr)
            continue
        if low == "/status":
            print_status_panel(
                llm_summary=summary,
                n_tools=len(agent.tool_names),
                session_key=session_key,
                skill_ok=skill_ok,
            )
            continue
        if low == "/tools":
            names = sorted(agent.tool_names)
            print(f"  {len(names)} tools:", file=sys.stderr)
            for i in range(0, len(names), 4):
                print("   ", "  ".join(names[i : i + 4]), file=sys.stderr)
            print(file=sys.stderr)
            continue
        if low in ("/new", "/reset"):
            session_key = f"chat-{os.getpid()}-{int(__import__('time').time())}"
            print(f"  ✓ new session · {session_key}", file=sys.stderr)
            continue
        if low == "/clear":
            sys.stderr.write("\033[2J\033[H")
            sys.stderr.flush()
            print_chat_header(
                llm_summary=summary,
                n_tools=len(agent.tool_names),
                skill_ok=skill_ok,
                session_key=session_key,
            )
            continue
        if low == "/thinking":
            cur = os.environ.get("RBP_SHOW_THINKING", "").strip().lower() in (
                "1",
                "true",
                "yes",
                "full",
                "expand",
            )
            if cur:
                os.environ.pop("RBP_SHOW_THINKING", None)
                print("  thinking folded (default)", file=sys.stderr)
            else:
                os.environ["RBP_SHOW_THINKING"] = "1"
                print("  thinking expanded", file=sys.stderr)
            continue
        if low in ("/onboard", "/login"):
            from rbp_agent.core.onboard import interactive_onboard

            interactive_onboard()
            try:
                from rbp_agent.core.onboard import current_summary

                summary = current_summary()
            except Exception:
                pass
            continue

        try:
            from nanobot.agent.tools.rbp.annotation import reset_tool_turn_guards

            reset_tool_turn_guards()
        except Exception:
            pass

        prompt = (
            msg
            + "\n\n[Output contract] Reply with ONE raw JSON object only "
            "(no markdown fences, no nested JSON). Fields: label, p_hat, "
            "confidence, explanation (plain sentences), supporting_rbps. "
            "If resolve_rbp.in_panel=true: own-head predict once then STOP. "
            "`p_hat` comes only from predict tools."
        )
        t0 = __import__("time").perf_counter()
        try:
            result = run_agent_turn_streamed_sync(
                agent, prompt, session_key=session_key, extra_hooks=[]
            )
        except KeyboardInterrupt:
            print("\n  ⚠ interrupted — ready for next message", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  ✗ error: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        print_verdict_block(format_verdict_display(result))
        elapsed = float(getattr(result, "_ux_elapsed", None) or (time.perf_counter() - t0))
        n_tools = len(getattr(result, "_ux_tools", None) or [])
        print_turn_footer(
            elapsed_s=elapsed,
            mode=getattr(result, "mode", "") or "",
            n_tools=n_tools,
        )


def cmd_nanobot_smoke(args: argparse.Namespace) -> int:
    from rbp_agent.integrate import RBPAgent

    agent = RBPAgent(allow_fallback=False, prefer_nanobot_llm=True)
    try:
        bot = agent.get_nanobot()
    except Exception as e:
        print(f"nanobot start failed: {e}")
        return 1
    print(f"tools={agent.tool_names}")
    print(f"bot={type(bot).__name__}")
    return 0 if agent.tool_names else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rbp-agent",
        description="RNA–RBP agent (nanobot + delivery tools). True agent path only.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="Check delivery paths + resolve_rbp smoke")
    d.set_defaults(func=cmd_doctor)

    g = sub.add_parser(
        "gate",
        help="Phase-1 engineering gate: ruff + pytest + layout (+ light eval if delivery)",
    )
    g.add_argument(
        "--skip-eval",
        action="store_true",
        help="Skip light LOO / eval-plan even if DELIVERY_ROOT is ready",
    )
    g.add_argument(
        "--no-cov",
        action="store_true",
        help="Run pytest without coverage fail-under",
    )
    g.set_defaults(func=cmd_gate)

    o = sub.add_parser("onboard", help="Configure LLM provider + API key + model")
    o.add_argument(
        "--provider",
        default=None,
        help="Non-interactive: registry name (openai|anthropic|deepseek|gemini|…)",
    )
    o.add_argument("--model", default=None, help="Model id (required with --provider)")
    o.add_argument("--key", default=None, help="API key")
    o.add_argument("--api-base", default=None, help="OpenAI-compatible base URL (custom providers)")
    o.add_argument("--show", action="store_true", help="Print active provider/model")
    o.add_argument(
        "--list-models",
        action="store_true",
        help="List curated provider → model choices and exit",
    )
    o.set_defaults(func=cmd_onboard)

    m = sub.add_parser("mvp", help="MVP acceptance (Nanobot.run required)")
    m.set_defaults(func=cmd_mvp)

    oh = sub.add_parser(
        "own-head",
        help="Ideal-env: delivery own-head on examples/sample_rna_pos (no LLM)",
    )
    oh.set_defaults(func=cmd_own_head)

    evo = sub.add_parser("evolve", help="Offline self-evolution")
    evo.add_argument("--top-k", type=int, default=5)
    from rbp_agent.core.paths import DEFAULT_EVAL_TRACE, DEFAULT_VAL_BATCH

    evo.add_argument("--trace", default=str(DEFAULT_EVAL_TRACE))
    evo.add_argument("--out", default=str(DEFAULT_VAL_BATCH))
    evo.add_argument(
        "--with-esm",
        action="store_true",
        help="Also call esm_similarity in LOO val (needs protein_embed + RAM)",
    )
    evo.add_argument(
        "--with-labels",
        default=None,
        help="JSON path: [{p_hat,y},…] for label-threshold CE retune",
    )
    evo.set_defaults(func=cmd_evolve)

    ee = sub.add_parser(
        "evolve-eval",
        help="Light nested-split eval of self-evolution (defaults vs retuned on held-out half)",
    )
    ee.add_argument("--seed", type=int, default=42)
    ee.add_argument("--n-test", type=int, default=5)
    ee.add_argument("--top-k", type=int, default=5)
    ee.add_argument(
        "--with-esm",
        action="store_true",
        help="Also fetch ESM hits (needs protein_embed + RAM)",
    )
    ee.add_argument("--no-live", action="store_true", help="Skip scoring live evolved.yaml")
    ee.add_argument(
        "--tier-a-ok",
        choices=["true", "false"],
        default=None,
        help="Override Tier A gate result for promote recommendation",
    )
    from rbp_agent.core.paths import REPORTS as _REPORTS

    ee.add_argument("--out", default=str(_REPORTS / "evolve_eval_report.json"))
    ee.add_argument("--md", default=str(_REPORTS / "evolve_eval_report.md"))
    ee.set_defaults(func=cmd_evolve_eval)

    pe = sub.add_parser(
        "promote-evolved",
        help="Promote evolved.candidate.yaml → evolved.yaml after light LOO/eval-plan gate",
    )
    pe.add_argument(
        "--force",
        action="store_true",
        help="Skip report asserts (dangerous; for offline fixtures only)",
    )
    pe.set_defaults(func=cmd_promote_evolved)

    ep = sub.add_parser(
        "eval-plan",
        help="Evaluation Plan: held-out LOO + ablations + AUROC/AUPRC/ECE report",
    )
    ep.add_argument("--with-seq", action="store_true")
    ep.add_argument("--labels", default=None, help="JSON [{p_hat,y},…] for instance metrics")
    from rbp_agent.core.paths import REPORTS

    ep.add_argument(
        "--out",
        default=str(REPORTS / "evaluation_plan_report.json"),
    )
    ep.set_defaults(func=cmd_eval_plan)

    c = sub.add_parser("compliance", help="Delivery path self-check")
    c.set_defaults(func=cmd_compliance)

    lay = sub.add_parser("layout", help="Assert plugin SoT layout + Runtime ($NANOBOT_SRC) import")
    lay.set_defaults(func=cmd_layout)

    n = sub.add_parser("nanobot-smoke", help="Register tools + start Nanobot")
    n.set_defaults(func=cmd_nanobot_smoke)

    a = sub.add_parser("agent", help="PRIMARY: one-shot Nanobot.run")
    a.add_argument("--message", default=None)
    a.add_argument(
        "--example",
        choices=["pos", "neg"],
        default=None,
        help="Delivery golden RNA (agent/examples) × PTBP1 own-head path",
    )
    a.add_argument("--query", default=None)
    a.add_argument("--uniprot", default=None)
    a.add_argument("--sequence-fasta", default=None)
    a.add_argument("--rna-file", default=None)
    a.add_argument("--force-transfer", action="store_true")
    a.add_argument("--strict", action="store_true", help="Exit 2 unless mode=nanobot_llm")
    a.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Science tools device (default: auto → cuda if available)",
    )
    a.add_argument("--session-key", default="rbp:cli")
    a.add_argument("--out", default=None)
    a.add_argument("--fallback", action="store_true", help=argparse.SUPPRESS)
    a.add_argument("--offline", action="store_true", help=argparse.SUPPRESS)
    a.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also show framework DEBUG logs (agent steps always shown)",
    )
    a.set_defaults(func=cmd_agent)

    chat = sub.add_parser(
        "chat",
        help="Multi-turn agent (thinking/tools + JSON verdict; logs quiet)",
    )
    chat.add_argument("--session-key", default=None)
    chat.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Science tools device (default: auto → cuda if available)",
    )
    chat.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also show framework DEBUG logs (agent steps always shown)",
    )
    chat.set_defaults(func=cmd_chat)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
