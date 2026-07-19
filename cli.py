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
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
BIO_ROOT = Path(os.environ.get("BIO_ROOT", ROOT.parent)).expanduser().resolve()
os.environ.setdefault("BIO_ROOT", str(BIO_ROOT))
os.environ.setdefault("NANOBOT_BIO_ROOT", str(ROOT))
os.environ.setdefault("NANOBOT_SRC", str(BIO_ROOT / "nanobot"))

# Sibling nanobot runtime first, then agent package (see activate_env.sh)
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
    from backends.delivery.client import DeliveryToolClient, SCRIPT_MAP, tools_meta_by_name
    from backends.delivery.env import apply_delivery_env, resolve_delivery_paths
    from core.chat_ux import cgroup_memory_gb, memory_blocker_message

    apply_delivery_env()
    paths = resolve_delivery_paths()
    print("=== rbp-agent doctor ===")
    print(f"DELIVERY_ROOT={paths['delivery_root']}")
    for k in ("rbp_registry", "predict_api", "registry_json", "agent_db", "rhobind_release"):
        p = paths[k]
        print(f"  {k}: {'OK' if p.exists() else 'MISSING'}  {p}")

    meta = tools_meta_by_name()
    print(f"delivery registry tools: {len(meta)}")
    missing = [n for n in SCRIPT_MAP if not (paths["delivery_root"] / SCRIPT_MAP[n]).is_file()]
    print(f"SCRIPT_MAP: {len(SCRIPT_MAP)}  missing: {len(missing)}")

    gb = cgroup_memory_gb()
    print(f"cgroup memory.max: {'unlimited' if gb is None else f'{gb:.2f} GiB'}")
    mem_warn = memory_blocker_message()
    if mem_warn:
        print(mem_warn)

    rhobind_py = None
    try:
        from backends.delivery.client import DeliveryToolClient as _DTC

        pref = _DTC._conda_env_prefix("rhobind")
        if pref is not None:
            cand = pref / "bin" / "python"
            if cand.is_file():
                rhobind_py = cand
    except Exception:
        pass
    print(
        f"rhobind python: {'OK' if rhobind_py else 'MISSING'}  "
        f"{rhobind_py or '(install via delivery setup_envs.sh)'}"
    )

    cli = DeliveryToolClient(offline=True, device="cpu", use_conda=False)
    r = cli.call("resolve_rbp", {"query": "PTBP1"})
    print(f"resolve_rbp(PTBP1): matched={r.get('matched')} alias={r.get('alias')}")
    print(
        f"Stage-0 ready: in_panel={r.get('in_panel')} "
        f"head_index={r.get('head_index')}"
    )
    try:
        from backends.delivery.examples import load_example

        ex = load_example("pos")
        print(f"golden example pos: rna_len={len(ex['rna'])} path={ex['rna_path']}")
    except Exception as e:
        print(f"golden example pos: MISSING ({e})")

    skill = ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md"
    skill_ok = skill.is_file() and "always: true" in skill.read_text(encoding="utf-8")
    print(f"SKILL always-on: {'OK' if skill_ok else 'FAIL'}")

    ok_bridge = bool(r.get("matched") and r.get("in_panel") and skill_ok)
    if ok_bridge and mem_warn:
        print("doctor: WARN (Stage-0 wiring OK; RhoBind may OOM until memory raised)")
        return 0
    if ok_bridge:
        print("doctor: OK")
        return 0
    print("doctor: FAIL")
    return 1


def cmd_onboard(args: argparse.Namespace) -> int:
    """Configure LLM provider + API key + model (writes nanobot config)."""
    from core.onboard import (
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
    from scripts.mvp_accept import main as mvp_main

    return int(mvp_main())


def cmd_own_head(args: argparse.Namespace) -> int:
    """Ideal-env scientific accept: delivery own-head on sample_rna_pos (no LLM)."""
    from scripts.own_head_accept import main as own_main

    return int(own_main())


def cmd_evolve(args: argparse.Namespace) -> int:
    from rbp_eval.evaluator import run_self_evolution

    out = run_self_evolution(
        top_k=int(getattr(args, "top_k", 5) or 5),
        trace_path=Path(getattr(args, "trace", None) or "rbp_eval/traces/loo_val.jsonl"),
        out_json=Path(getattr(args, "out", None) or "rbp_eval/traces/val_batch_results.json"),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False)[:2000])
    return 0


def cmd_compliance(args: argparse.Namespace) -> int:
    path = ROOT / "scripts" / "compliance_check.py"
    return int(subprocess.call([sys.executable, str(path)], cwd=str(ROOT)))


def cmd_agent(args: argparse.Namespace) -> int:
    """One-shot Nanobot.run (proposal primary path). No pipeline fallback."""
    from core.chat_ux import (
        configure_chat_logging,
        format_verdict_display,
        memory_blocker_message,
        print_banner,
        print_registration,
        print_verdict_block,
        run_agent_turn_streamed_sync,
    )
    from integrate import skill_path as _skill_path

    configure_chat_logging(verbose=bool(getattr(args, "verbose", False)))
    print_banner(subtitle="one-shot agent · thinking + tools visible")
    warn = memory_blocker_message()
    if warn:
        print(warn, file=sys.stderr)

    try:
        from integrate import RBPAgent
    except ImportError as e:
        print("integrate import failed:", e, file=sys.stderr)
        return 1

    try:
        from rbp_eval.nanobot_hooks import RBPTraceHook
    except ImportError:
        from rbp_eval.hooks import JsonlTraceHook as RBPTraceHook

    if getattr(args, "example", None):
        from backends.delivery.examples import own_head_prompt

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
            "Use Nanobot agent path only. Offline fixture: rbp_eval/fixtures if needed.",
            file=sys.stderr,
        )
        return 2

    trace = ROOT / "rbp_eval" / "traces" / "cli_agent.jsonl"
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
        "Never invent p_hat."
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
    from core.chat_ux import (
        configure_chat_logging,
        format_verdict_display,
        memory_blocker_message,
        print_chat_header,
        print_registration,
        print_verdict_block,
        read_user_message,
        run_agent_turn_streamed_sync,
    )
    from integrate import skill_path as _skill_path

    verbose = bool(getattr(args, "verbose", False))
    configure_chat_logging(verbose=verbose)

    try:
        from integrate import RBPAgent
    except ImportError as e:
        print("Failed to import integrate:", e, file=sys.stderr)
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
    trace = ROOT / "rbp_eval" / "traces" / "cli_chat.jsonl"

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
        from core.onboard import current_summary

        summary = current_summary()
    except Exception:
        summary = "?"

    skill = _skill_path()
    print_chat_header(
        llm_summary=summary,
        n_tools=len(agent.tool_names),
        skill_ok=bool(skill and skill.is_file()),
        mem_warn=memory_blocker_message(),
    )
    print_registration(agent.tool_names, skill_path=skill)

    while True:
        msg = read_user_message("you › ")
        if msg is None:
            print()
            return 0
        if not msg:
            continue
        low = msg.lower()
        if low in ("/quit", "/exit", "quit", "exit"):
            return 0
        if low in ("/new", "/reset"):
            session_key = f"chat-{os.getpid()}-{int(__import__('time').time())}"
            print(f"new session · {session_key}", file=sys.stderr)
            continue
        if low in ("/onboard", "/login"):
            from core.onboard import interactive_onboard

            interactive_onboard()
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
            "Never invent p_hat."
        )
        try:
            result = run_agent_turn_streamed_sync(
                agent, prompt, session_key=session_key, extra_hooks=[]
            )
        except Exception as e:
            print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        print_verdict_block(format_verdict_display(result))


def cmd_nanobot_smoke(args: argparse.Namespace) -> int:
    from integrate import RBPAgent

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

    evo = sub.add_parser("evolve", help="Offline self-evolution (§7)")
    evo.add_argument("--top-k", type=int, default=5)
    evo.add_argument("--trace", default="rbp_eval/traces/loo_val.jsonl")
    evo.add_argument("--out", default="rbp_eval/traces/val_batch_results.json")
    evo.set_defaults(func=cmd_evolve)

    c = sub.add_parser("compliance", help="Delivery path self-check")
    c.set_defaults(func=cmd_compliance)

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
