# -*- coding: utf-8 -*-
"""User-facing commands: doctor, onboard, agent, chat, nanobot-smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from app.cli.common import ROOT, read_fasta

def cmd_agent(args: argparse.Namespace) -> int:
    """One-shot Nanobot.run (primary agent path). No pipeline fallback."""
    from app.core.chat_ux import (
        configure_chat_logging,
        format_verdict_display,
        memory_blocker_message,
        print_banner,
        print_registration,
        print_verdict_block,
        run_agent_turn_streamed_sync,
    )
    from app.agent import skill_path as _skill_path

    configure_chat_logging(verbose=bool(getattr(args, "verbose", False)))
    print_banner(subtitle="one-shot agent · thinking + tools visible")
    warn = memory_blocker_message()
    if warn:
        print(warn, file=sys.stderr)

    try:
        from app.agent import RBPAgent
    except ImportError as e:
        print("integrate import failed:", e, file=sys.stderr)
        return 1

    try:
        from rbp_eval.nanobot_hooks import RBPTraceHook
    except ImportError:
        from rbp_eval.hooks import JsonlTraceHook as RBPTraceHook

    if getattr(args, "example", None):
        from app.backends.delivery.examples import own_head_prompt

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
            seq = read_fasta(Path(args.sequence_fasta))
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

    from app.core.paths import TRACES, ensure_artifact_dirs

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
    from app.core.chat_ux import (
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
    from app.agent import skill_path as _skill_path

    verbose = bool(getattr(args, "verbose", False))
    configure_chat_logging(verbose=verbose)

    try:
        from app.agent import RBPAgent
    except ImportError as e:
        print("Failed to import app.agent:", e, file=sys.stderr)
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
    from app.core.paths import TRACES, ensure_artifact_dirs

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
        from app.core.onboard import current_summary

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
            from app.core.onboard import interactive_onboard

            interactive_onboard()
            try:
                from app.core.onboard import current_summary

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


def cmd_doctor(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from app.backends.delivery.client import DeliveryToolClient, SCRIPT_MAP, tools_meta_by_name
    from app.backends.delivery.env import apply_delivery_env, resolve_delivery_paths
    from app.core.chat_ux import cgroup_memory_gb, memory_blocker_message
    from app.core.paths import ARTIFACTS, REPORTS, ensure_artifact_dirs

    apply_delivery_env()
    sync_ok = False
    sync_err = None
    try:
        from app.sync_overlay import sync_overlay

        sync_ok = sync_overlay(quiet=True) == 0
    except Exception as e:
        sync_err = f"{type(e).__name__}: {e}"
    dirs = ensure_artifact_dirs()
    paths = resolve_delivery_paths()
    print("=== nanobot-bio doctor ===")
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
        from app.backends.delivery.client import DeliveryToolClient as _DTC

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
        from app.backends.delivery.examples import load_example

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

    try:
        from app.backends.delivery.stage_tools import (
            assert_full_axes_enabled,
            axis_status_matrix,
        )
        from app.core.runtime_config import load_runtime_config

        _cfg = load_runtime_config()
        _axes = _cfg.get("axes") or {}
        _off = assert_full_axes_enabled(_axes)
        _st = axis_status_matrix(_axes)
        print(
            "axes: "
            + (
                "OK (required on)"
                if not _off
                else f"REQUIRED_OFF={','.join(_off)}"
            )
            + f"  use_af3={_axes.get('use_af3')}  af3_runtime={_st.get('use_af3', 'n/a')}"
        )
        for k, v in _st.items():
            if v != "ready":
                print(f"  axis {k}: {v}")
    except Exception as e:
        print(f"axes: FAIL ({type(e).__name__}: {e})")

    matrix_path = None
    try:
        from app.core.model_registry import write_capability_matrix

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
    try:
        from app.backends.delivery.stage_tools import (
            assert_full_axes_enabled,
            axis_status_matrix,
        )
        from app.core.runtime_config import load_runtime_config

        _cfg = load_runtime_config()
        _axes = dict(_cfg.get("axes") or {})
        report["axes"] = {
            "required_off": assert_full_axes_enabled(_axes),
            "use_af3": bool(_axes.get("use_af3")),
            "status": axis_status_matrix(_axes),
            "prefer_afdb": (_cfg.get("structure_policy") or {}).get("prefer_afdb"),
        }
    except Exception as e:
        report["axes"] = {"error": f"{type(e).__name__}: {e}"}
    out = REPORTS / "doctor_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"doctor report: {out}")
    return rc


def cmd_nanobot_smoke(args: argparse.Namespace) -> int:
    from app.agent import RBPAgent

    agent = RBPAgent(allow_fallback=False, prefer_nanobot_llm=True)
    try:
        bot = agent.get_nanobot()
    except Exception as e:
        print(f"nanobot start failed: {e}")
        return 1
    print(f"tools={agent.tool_names}")
    print(f"bot={type(bot).__name__}")
    return 0 if agent.tool_names else 1


def cmd_onboard(args: argparse.Namespace) -> int:
    """Configure LLM provider + API key + model (writes nanobot config)."""
    from app.core.onboard import (
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

