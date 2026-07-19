# -*- coding: utf-8 -*-
"""Chat UX: quiet framework logs + visible agent steps + terminal chrome."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, TextIO


# ---------------------------------------------------------------------------
# ANSI / chrome
# ---------------------------------------------------------------------------

def _use_color(stream: TextIO = sys.stderr) -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("RBP_NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


class Style:
    """Lightweight ANSI styles (disabled on non-TTY / NO_COLOR)."""

    def __init__(self, stream: TextIO = sys.stderr) -> None:
        self.on = _use_color(stream)
        self.stream = stream

    def _s(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def dim(self, t: str) -> str:
        return self._s("2", t)

    def bold(self, t: str) -> str:
        return self._s("1", t)

    def cyan(self, t: str) -> str:
        return self._s("36", t)

    def green(self, t: str) -> str:
        return self._s("32", t)

    def yellow(self, t: str) -> str:
        return self._s("33", t)

    def red(self, t: str) -> str:
        return self._s("31", t)

    def magenta(self, t: str) -> str:
        return self._s("35", t)


def _term_width(default: int = 72) -> int:
    try:
        return max(48, min(100, os.get_terminal_size().columns))
    except OSError:
        return default


def print_banner(
    title: str = "RNA–RBP Agent",
    subtitle: str = "nanobot · delivery tools · Stage 0–3",
    *,
    stream: TextIO = sys.stderr,
) -> None:
    """Top-of-session brand line."""
    s = Style(stream)
    w = _term_width()
    bar = "─" * w
    stream.write(s.cyan(bar) + "\n")
    stream.write(s.bold(s.cyan(f"  {title}")) + "\n")
    stream.write(s.dim(f"  {subtitle}") + "\n")
    stream.write(s.cyan(bar) + "\n")
    stream.flush()


def print_chat_header(
    *,
    llm_summary: str,
    n_tools: int,
    skill_ok: bool,
    mem_warn: Optional[str] = None,
    stream: TextIO = sys.stderr,
) -> None:
    s = Style(stream)
    print_banner(stream=stream)
    skill = s.green("always-on") if skill_ok else s.red("missing")
    stream.write(f"  LLM     {s.bold(llm_summary)}\n")
    stream.write(f"  Tools   {s.bold(str(n_tools))} registered\n")
    stream.write(f"  Skill   rbp-agent ({skill})\n")
    stream.write(
        s.dim(
            "  Commands  /quit  /new  /onboard  ·  "
            "thoughts fold by default (RBP_SHOW_THINKING=1 to expand)\n"
        )
    )
    if mem_warn:
        stream.write(s.yellow(f"\n  {mem_warn}\n"))
    stream.write("\n")
    stream.flush()


def print_registration(
    tool_names: list[str],
    *,
    skill_path: Optional[Path] = None,
    stream: TextIO = sys.stderr,
) -> None:
    """Show tool/skill registration before the agent loop."""
    s = Style(stream)
    stream.write(s.bold(s.cyan("▸ register")) + s.dim("  agent API / tools\n"))
    if skill_path:
        stream.write(s.dim(f"  skill  {skill_path}\n"))
    # Group for readability
    stage0 = {"resolve_rbp", "predict_interaction", "near_match_identity"}
    shown = sorted(tool_names)
    primary = [n for n in shown if n in stage0 or n.startswith(("transfer", "seq_", "domain", "structure", "literature", "get_func", "fuse", "integrate"))]
    rest = [n for n in shown if n not in primary]
    line = ", ".join(primary[:12] or shown[:12])
    if len(shown) > 12:
        line += f", … (+{len(shown) - 12})"
    stream.write(f"  {s.green('✓')} {len(shown)} tools  {s.dim(line)}\n")
    if rest and len(primary) >= 8:
        stream.write(s.dim(f"  + {len(rest)} delivery extras\n"))
    stream.write("\n")
    stream.flush()


def print_verdict_block(body: str, *, stream: TextIO = sys.stdout) -> None:
    s = Style(stream)
    w = _term_width()
    stream.write(s.bold(s.green("▸ verdict")) + "\n")
    stream.write(s.dim("─" * min(w, 40)) + "\n")
    stream.write(body if body.endswith("\n") else body + "\n")
    stream.write(s.dim("─" * min(w, 40)) + "\n")
    stream.flush()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def configure_chat_logging(*, verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """Silence nanobot/loguru DEBUG on the terminal; keep DETAIL in a file."""
    from loguru import logger

    logger.remove()
    if verbose:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<level>{level: <5}</level> | <level>{message}</level>",
            colorize=True,
        )
    else:
        logger.add(
            sys.stderr,
            level="ERROR",
            format="<level>{level}</level> | <level>{message}</level>",
            colorize=True,
            filter=lambda r: "LLM transient error" not in str(r.get("message") or ""),
        )
    if log_file is None:
        log_file = Path(
            os.environ.get("RBP_CHAT_LOG", "rbp_eval/traces/cli_chat.log")
        )
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_file),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <5} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention=3,
    )


# ---------------------------------------------------------------------------
# Input (prompt_toolkit — same stack as nanobot agent CLI)
# ---------------------------------------------------------------------------

_PROMPT_SESSION: Any = None


def _init_prompt_session(history_dir: Optional[Path] = None) -> None:
    """Create a PromptSession with file history under workspace/sessions."""
    global _PROMPT_SESSION
    if _PROMPT_SESSION is not None:
        return
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
    except ImportError:
        _PROMPT_SESSION = False  # type: ignore[assignment]
        return

    base = history_dir or Path(
        os.environ.get("NANOBOT_WORKSPACE", "workspace")
    ) / "sessions"
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    hist = base / "rbp_chat_history"
    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(hist)),
        enable_open_in_editor=False,
        multiline=False,
    )


def read_user_message(prompt: str = "you › ") -> Optional[str]:
    """Read one chat turn via prompt_toolkit (history + paste); fallback to input()."""
    _init_prompt_session()
    if _PROMPT_SESSION and _PROMPT_SESSION is not False:
        try:
            from prompt_toolkit.formatted_text import HTML
            from prompt_toolkit.patch_stdout import patch_stdout

            with patch_stdout():
                # Brand tweak of nanobot's blue "You:" prompt
                text = _PROMPT_SESSION.prompt(
                    HTML(f"<b fg='ansicyan'>{prompt}</b>"),
                )
            return (text or "").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        except Exception:
            pass

    s = Style(sys.stdout)
    try:
        first = input(s.cyan(prompt) if s.on else prompt)
    except (EOFError, KeyboardInterrupt):
        return None
    return (first or "").strip()


# ---------------------------------------------------------------------------
# Spinner — adapter over nanobot.cli.stream.ThinkingSpinner
# ---------------------------------------------------------------------------

class ThinkingSpinner:
    """Wrap nanobot Rich status spinner; expose pause/resume for tool traces."""

    def __init__(self, label: str = "thinking", bot_name: str = "rbp-agent") -> None:
        self._label = label
        self._hint = ""
        self._pause_cm: Any = None
        self._enabled = sys.stderr.isatty() and not os.environ.get("RBP_NO_SPINNER")
        self._inner: Any = None
        if self._enabled:
            try:
                from nanobot.cli.stream import ThinkingSpinner as _NBSpinner

                self._inner = _NBSpinner(bot_name=bot_name)
            except Exception:
                self._enabled = False

    def update(self, hint: str) -> None:
        self._hint = (hint or "").strip()[:48]

    def pause(self) -> None:
        if not self._inner or self._pause_cm is not None:
            return
        self._pause_cm = self._inner.pause()
        self._pause_cm.__enter__()

    def resume(self) -> None:
        if self._pause_cm is None:
            return
        self._pause_cm.__exit__(None, None, None)
        self._pause_cm = None

    def __enter__(self) -> "ThinkingSpinner":
        if self._inner:
            self._inner.__enter__()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.resume()
        if self._inner:
            self._inner.__exit__(*exc)
        return None


# ---------------------------------------------------------------------------
# Agent step trace (thinking + tools)
# ---------------------------------------------------------------------------

def _short_json(obj: Any, limit: int = 120) -> str:
    try:
        raw = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        raw = str(obj)
    raw = raw.replace("\n", " ")
    if len(raw) > limit:
        return raw[: limit - 1] + "…"
    return raw


def _summarize_tool_result(result: Any) -> str:
    """Compact status line from delivery envelope or plain result."""
    text = result
    if isinstance(result, dict) and "content" in result:
        text = result.get("content")
    if isinstance(text, str):
        try:
            text = json.loads(text)
        except Exception:
            t = text.replace("\n", " ").strip()
            return (t[:100] + "…") if len(t) > 100 else t
    if isinstance(text, dict):
        st = text.get("status")
        if st == "ok":
            val = text.get("value")
            if isinstance(val, dict):
                bits = []
                for k in ("in_panel", "alias", "matched", "path", "stop_hint"):
                    if k in val:
                        bits.append(f"{k}={val[k]}")
                preds = val.get("predictions")
                if isinstance(preds, list) and preds:
                    p0 = preds[0] if isinstance(preds[0], dict) else {}
                    if "prob" in p0:
                        bits.append(f"prob={p0.get('prob')}")
                if bits:
                    return "ok · " + ", ".join(str(b) for b in bits[:5])
            return "ok · " + _short_json(val, 90)
        if st == "error":
            return f"error · {text.get('reason') or text.get('message') or 'failed'}"
        return _short_json(text, 100)
    return _short_json(text, 100)


def _show_full_thinking() -> bool:
    """Expand folded thoughts (Cursor-style default = collapsed)."""
    return os.environ.get("RBP_SHOW_THINKING", "").strip().lower() in (
        "1", "true", "yes", "full", "expand",
    )


def _slim_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    prefer = (
        "rbp_id", "rbps", "query", "uniprot", "alias", "name",
        "cohort", "rna", "sequence", "target", "encoder", "device",
    )
    slim: dict[str, Any] = {}
    for k in prefer:
        if k not in args:
            continue
        v = args[k]
        if k in ("rna", "sequence") and isinstance(v, str) and len(v) > 24:
            unit = "nt" if k == "rna" else "aa"
            slim[k] = f"{v[:12]}…({len(v)}{unit})"
        else:
            slim[k] = v
    if not slim:
        slim = {k: args[k] for k in list(args)[:4]}
    return slim


def make_agent_trace_hook(
    *,
    spinner: Optional[ThinkingSpinner] = None,
    stream: TextIO = sys.stderr,
    show_args: bool = True,
):
    """AgentHook: tools visible; thinking buffered then folded (Cursor-like).

    Live token spam is suppressed. Full thought text only when
    ``RBP_SHOW_THINKING=1`` (also saved under workspace/sessions/).
    """
    from nanobot.agent.hook import AgentHook, AgentHookContext, AgentRunHookContext

    class _AgentTraceHook(AgentHook):
        def __init__(self) -> None:
            super().__init__()
            self._s = Style(stream)
            self._thought_parts: list[str] = []
            self._thought_t0: Optional[float] = None
            self._thought_folded = False
            self._tools_this_run: list[str] = []
            self._step = 0

        def _out(self, line: str) -> None:
            if spinner:
                spinner.pause()
            stream.write(line + "\n")
            stream.flush()
            if spinner:
                spinner.resume()

        def _thought_text(self) -> str:
            return "".join(self._thought_parts).strip()

        def _save_thought(self, text: str) -> Optional[Path]:
            if not text:
                return None
            try:
                base = Path(
                    os.environ.get("NANOBOT_WORKSPACE", "workspace")
                ) / "sessions"
                base.mkdir(parents=True, exist_ok=True)
                path = base / "last_thinking.txt"
                path.write_text(text + "\n", encoding="utf-8")
                return path
            except OSError:
                return None

        def _fold_thought(self) -> None:
            """Replace live thinking with one Cursor-like collapsed line."""
            if self._thought_folded:
                return
            text = self._thought_text()
            if not text and self._thought_t0 is None:
                return
            self._thought_folded = True
            elapsed = 0.0
            if self._thought_t0 is not None:
                elapsed = max(0.0, time.perf_counter() - self._thought_t0)
            path = self._save_thought(text)
            preview = " ".join(text.split())
            if len(preview) > 96:
                preview = preview[:95] + "…"
            # Collapsed header (always)
            self._out(
                f"  {self._s.magenta('✻')} {self._s.bold('Thought')}"
                + self._s.dim(f"  ·  {elapsed:.1f}s  ·  folded")
                + (self._s.dim(f"  ·  {len(text)} chars") if text else "")
            )
            if preview:
                self._out(self._s.dim(f"      {preview}"))
            if _show_full_thinking() and text:
                self._out(self._s.dim("      ── full thinking ──"))
                for ln in text.splitlines() or [text]:
                    self._out(self._s.dim(f"      {ln}"))
                self._out(self._s.dim("      ──────────────────"))
            elif path is not None:
                self._out(
                    self._s.dim(
                        f"      full: {path}  ·  expand: RBP_SHOW_THINKING=1"
                    )
                )
            self._thought_parts.clear()
            self._thought_t0 = None

        async def before_run(self, context: AgentRunHookContext) -> None:
            self._tools_this_run.clear()
            self._step = 0
            self._thought_parts.clear()
            self._thought_folded = False
            self._thought_t0 = None
            self._out(self._s.bold(self._s.cyan("▸ agent")) + self._s.dim("  start"))

        async def before_iteration(self, context: AgentHookContext) -> None:
            n = context.iteration + 1
            if spinner:
                spinner.update(f"turn {n}")
            self._out(self._s.bold(f"── turn {n} ──"))
            # New model turn may bring a new thought block
            self._thought_folded = False

        async def emit_reasoning(self, reasoning_content: str | None) -> None:
            # Buffer only — never print per-token (that made the CLI ugly/slow).
            if not reasoning_content:
                return
            if self._thought_t0 is None:
                self._thought_t0 = time.perf_counter()
            self._thought_parts.append(reasoning_content)
            if spinner:
                spinner.update("thinking")

        async def emit_reasoning_end(self) -> None:
            self._fold_thought()

        async def before_execute_tools(self, context: AgentHookContext) -> None:
            # Non-streaming models put a plan in response.content
            resp = context.response
            thought = (getattr(resp, "content", None) or "").strip() if resp else ""
            if thought and not context.streamed_reasoning and not self._thought_parts:
                self._thought_t0 = self._thought_t0 or time.perf_counter()
                self._thought_parts.append(thought)
            self._fold_thought()

            calls = list(context.tool_calls or [])
            if not calls:
                return
            self._out(self._s.dim("  tools"))
            for tc in calls:
                self._step += 1
                name = getattr(tc, "name", "?")
                self._tools_this_run.append(name)
                if spinner:
                    spinner.update(name)
                args = getattr(tc, "arguments", None) or {}
                arg_s = ""
                if show_args and isinstance(args, dict):
                    arg_s = _short_json(_slim_tool_args(args), 160)
                self._out(
                    f"  {self._s.yellow(f'{self._step:>2}.')} "
                    f"{self._s.bold(name)}"
                    + (self._s.dim(f"  {arg_s}") if arg_s else "")
                )

        async def after_iteration(self, context: AgentHookContext) -> None:
            self._fold_thought()
            results = list(context.tool_results or [])
            calls = list(context.tool_calls or [])
            events = list(context.tool_events or [])
            for i, tc in enumerate(calls):
                name = getattr(tc, "name", "tool")
                res = results[i] if i < len(results) else None
                if isinstance(res, tuple) and res:
                    res = res[0]
                ev = events[i] if i < len(events) and isinstance(events[i], dict) else {}
                if ev.get("status") == "error":
                    summary = f"error · {ev.get('detail') or _summarize_tool_result(res)}"
                    ok = False
                else:
                    summary = _summarize_tool_result(res) if res is not None else "—"
                    ok = not str(summary).startswith("error")
                mark = self._s.green("←") if ok else self._s.red("←")
                self._out(
                    f"  {mark} {self._s.bold(name) if ok else self._s.red(name)}"
                    f"  {self._s.dim(summary)}"
                )

            if spinner:
                spinner.update("thinking")

        async def after_run(self, context: AgentRunHookContext) -> None:
            self._fold_thought()
            used = list(context.tools_used or self._tools_this_run)
            if used:
                # Preserve order, unique
                seen: list[str] = []
                for n in used:
                    if n not in seen:
                        seen.append(n)
                self._out(
                    self._s.dim("▸ done")
                    + f"  {len(seen)} tools: "
                    + ", ".join(seen[:16])
                    + (f" (+{len(seen) - 16})" if len(seen) > 16 else "")
                )
            else:
                self._out(self._s.dim("▸ done"))

        async def on_error(self, context: AgentRunHookContext) -> None:
            self._fold_thought()
            err = context.error or (
                type(context.exception).__name__ if context.exception else "error"
            )
            self._out(self._s.red(f"▸ error  {err}"))

    return _AgentTraceHook()


def make_progress_hook(spinner: ThinkingSpinner):
    """Back-compat alias: full agent step trace driven by spinner."""
    return make_agent_trace_hook(spinner=spinner)


# ---------------------------------------------------------------------------
# Verdict display
# ---------------------------------------------------------------------------

def format_verdict_display(result: Any) -> str:
    """Pretty-print a clean proposal verdict JSON (unwrap nested fences)."""
    from core.verdict_schema import extract_verdict_from_content, normalize_verdict

    content = getattr(result, "content", None) or ""
    verdict = extract_verdict_from_content(content) if content else {}
    if not verdict.get("explanation"):
        verdict = normalize_verdict(getattr(result, "verdict", None) or {})

    display = {
        "label": verdict.get("label"),
        "p_hat": verdict.get("p_hat"),
        "confidence": verdict.get("confidence"),
        "explanation": verdict.get("explanation"),
        "supporting_rbps": verdict.get("supporting_rbps") or [],
    }
    return json.dumps(display, indent=2, ensure_ascii=False) + "\n"


def cgroup_memory_gb() -> Optional[float]:
    """Return cgroup memory.max in GiB, or None if unlimited / unknown."""
    for path in (
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    ):
        try:
            raw = path.read_text().strip()
        except OSError:
            continue
        if raw in ("max", ""):
            return None
        try:
            n = int(raw)
        except ValueError:
            continue
        if n >= 2**60:
            return None
        return n / (1024**3)
    return None


def memory_blocker_message(min_gb: float = 8.0) -> Optional[str]:
    """Advisory only: ideal GPU host needs enough RAM for RhoBind / ESM.

    Does not change agent behaviour or force CPU — product path still prefers
    CUDA via ``RHOBIND_DEVICE=auto``. Raise the cgroup / instance size before
    claiming scientific goldens.
    """
    gb = cgroup_memory_gb()
    if gb is not None and gb < min_gb:
        return (
            f"NOTE: cgroup memory.max ≈ {gb:.1f} GiB "
            f"(ideal env ≥ {min_gb:.0f} GiB RAM + CUDA for RhoBind/ESM). "
            "This host may OOM science tools (rc=137) → p_hat stays null "
            "(never invent scores). Upgrade instance for acceptance runs."
        )
    return None


def run_agent_turn_streamed_sync(
    agent: Any,
    prompt: str,
    *,
    session_key: str,
    extra_hooks: Optional[list[Any]] = None,
    bot_name: str = "rbp-agent",
) -> Any:
    """Sync helper: streamed run + Rich spinner + folded thought + tool steps.

    Final JSON is not printed here — caller uses ``print_verdict_block``.
    Answer tokens are not Live-rendered (JSON contract → verdict box only).
    """
    import asyncio

    from nanobot.cli.stream import ThinkingSpinner as NBSpinner

    # Spinner only (no Live markdown of JSON — keeps the UI clean/fast).
    nb_spinner = NBSpinner(bot_name=bot_name)

    class _Bridge:
        def __init__(self) -> None:
            self._cm: Any = None
            self._entered = False

        def update(self, hint: str) -> None:
            return None

        def pause(self) -> None:
            if self._cm is not None:
                return
            self._cm = nb_spinner.pause()
            self._cm.__enter__()

        def resume(self) -> None:
            if self._cm is None:
                return
            self._cm.__exit__(None, None, None)
            self._cm = None

        def __enter__(self) -> "_Bridge":
            nb_spinner.__enter__()
            self._entered = True
            return self

        def __exit__(self, *exc: Any) -> None:
            self.resume()
            if self._entered:
                nb_spinner.__exit__(*exc)
            return None

    bridge = _Bridge()
    progress = make_agent_trace_hook(spinner=bridge)
    hooks = [progress, *(extra_hooks or [])]
    with bridge:
        return asyncio.run(
            agent.run_streamed(
                prompt,
                session_key=session_key,
                extra_hooks=hooks,
                renderer=None,
            )
        )