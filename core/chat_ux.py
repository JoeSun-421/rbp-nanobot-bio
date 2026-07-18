# -*- coding: utf-8 -*-
"""Chat UX: quiet framework logs + visible agent steps + terminal chrome."""

from __future__ import annotations

import json
import os
import sys
import threading
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
        s.dim("  Commands  /quit  /new  /onboard  ·  agent steps shown below\n")
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
# Input
# ---------------------------------------------------------------------------

def read_user_message(prompt: str = "you › ") -> Optional[str]:
    """Read one chat turn; drain multi-line pastes from stdin."""
    import select

    s = Style(sys.stdout)
    try:
        first = input(s.cyan(prompt) if s.on else prompt)
    except (EOFError, KeyboardInterrupt):
        return None
    if first is None:
        return None
    stripped = first.strip()
    if not stripped:
        return ""
    if stripped.startswith("/") or stripped.lower() in ("quit", "exit"):
        return stripped

    lines = [first.rstrip("\n")]
    try:
        while select.select([sys.stdin], [], [], 0.08)[0]:
            nxt = sys.stdin.readline()
            if nxt == "":
                break
            if not nxt.strip():
                if len(lines) > 1:
                    break
                continue
            lines.append(nxt.rstrip("\n"))
    except (EOFError, KeyboardInterrupt, ValueError, OSError):
        pass
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Spinner (idle wait between hook events)
# ---------------------------------------------------------------------------

class ThinkingSpinner:
    """Braille spinner on stderr while the LLM is working."""

    def __init__(self, label: str = "thinking") -> None:
        self._label = label
        self._hint = ""
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._enabled = sys.stderr.isatty() and not os.environ.get("RBP_NO_SPINNER")
        self._paused = False

    def update(self, hint: str) -> None:
        self._hint = (hint or "").strip()[:48]

    def pause(self) -> None:
        """Clear spinner line so step logs are not overwritten."""
        self._paused = True
        if self._enabled:
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

    def resume(self) -> None:
        self._paused = False

    def __enter__(self) -> "ThinkingSpinner":
        if not self._enabled:
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self._enabled:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            if not self._paused:
                frame = self._frames[i % len(self._frames)]
                hint = f" · {self._hint}" if self._hint else ""
                sys.stderr.write(f"\r{frame} {self._label}{hint}")
                sys.stderr.flush()
            i += 1
            time.sleep(0.08)


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


def make_agent_trace_hook(
    *,
    spinner: Optional[ThinkingSpinner] = None,
    stream: TextIO = sys.stderr,
    show_args: bool = True,
):
    """AgentHook: print thinking + tool calls/results (framework logs stay quiet)."""
    from nanobot.agent.hook import AgentHook, AgentHookContext, AgentRunHookContext

    class _AgentTraceHook(AgentHook):
        def __init__(self) -> None:
            super().__init__()
            self._s = Style(stream)
            self._reasoning_buf: list[str] = []
            self._reasoning_open = False

        def _out(self, line: str) -> None:
            if spinner:
                spinner.pause()
            stream.write(line + "\n")
            stream.flush()
            if spinner:
                spinner.resume()

        async def before_run(self, context: AgentRunHookContext) -> None:
            self._out(self._s.bold(self._s.cyan("▸ agent")) + self._s.dim("  run start"))

        async def before_iteration(self, context: AgentHookContext) -> None:
            n = context.iteration + 1
            if spinner:
                spinner.update(f"turn {n}")
            self._out(
                self._s.bold(f"── turn {n} ──")
            )

        async def emit_reasoning(self, reasoning_content: str | None) -> None:
            if not reasoning_content:
                return
            self._reasoning_open = True
            self._reasoning_buf.append(reasoning_content)
            # Stream chunks live (dim)
            chunk = reasoning_content.replace("\n", " ").strip()
            if chunk:
                if spinner:
                    spinner.pause()
                stream.write(self._s.dim("  think  ") + self._s.magenta(chunk[:200]))
                if len(chunk) > 200:
                    stream.write(self._s.dim("…"))
                stream.write("\n")
                stream.flush()
                if spinner:
                    spinner.resume()

        async def emit_reasoning_end(self) -> None:
            self._reasoning_open = False
            self._reasoning_buf.clear()

        async def before_execute_tools(self, context: AgentHookContext) -> None:
            # Model "thought" text before tools (non-streaming models)
            resp = context.response
            thought = (getattr(resp, "content", None) or "").strip() if resp else ""
            if thought and not context.streamed_reasoning:
                # Truncate long pre-tool chatter; keep signal
                one = thought.replace("\n", " ")
                if len(one) > 220:
                    one = one[:219] + "…"
                self._out(self._s.dim("  think  ") + one)

            for tc in context.tool_calls or []:
                name = getattr(tc, "name", "?")
                if spinner:
                    spinner.update(name)
                args = getattr(tc, "arguments", None) or {}
                if show_args and isinstance(args, dict):
                    # Prefer short biologically relevant keys
                    prefer = (
                        "rbp_id", "rbps", "query", "uniprot", "alias",
                        "cohort", "rna", "sequence", "target",
                    )
                    slim: dict[str, Any] = {}
                    for k in prefer:
                        if k in args:
                            v = args[k]
                            if k == "rna" and isinstance(v, str) and len(v) > 24:
                                slim[k] = f"{v[:12]}…({len(v)}nt)"
                            elif k == "sequence" and isinstance(v, str) and len(v) > 24:
                                slim[k] = f"{v[:12]}…({len(v)}aa)"
                            else:
                                slim[k] = v
                    if not slim:
                        slim = {k: args[k] for k in list(args)[:4]}
                    arg_s = _short_json(slim, 140)
                else:
                    arg_s = ""
                self._out(
                    f"  {self._s.yellow('tool')}  {self._s.bold(name)}"
                    + (self._s.dim(f"  {arg_s}") if arg_s else "")
                )

        async def after_iteration(self, context: AgentHookContext) -> None:
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
                self._out(f"  {mark} {self._s.dim(name)}  {summary}")

            if spinner:
                spinner.update(f"turn {context.iteration + 1} done")

            # Final answer this turn (no more tools)
            if not calls and context.response is not None:
                final = (context.response.content or "").strip()
                if final and not context.tool_calls:
                    preview = final.replace("\n", " ")
                    if len(preview) > 160:
                        preview = preview[:159] + "…"
                    self._out(self._s.dim("  draft  ") + preview)

        async def after_run(self, context: AgentRunHookContext) -> None:
            used = context.tools_used or []
            if used:
                self._out(
                    self._s.dim("▸ done")
                    + f"  tools used: {', '.join(used[:12])}"
                    + (f" (+{len(used) - 12})" if len(used) > 12 else "")
                )
            else:
                self._out(self._s.dim("▸ done"))

        async def on_error(self, context: AgentRunHookContext) -> None:
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
    """If the container cannot run RhoBind, return a clear user-facing warning."""
    gb = cgroup_memory_gb()
    if gb is not None and gb < min_gb:
        return (
            f"WARNING: cgroup memory limit ≈ {gb:.1f} GiB "
            f"(need ≥ {min_gb:.0f} GiB for RhoBind). "
            "predict_interaction will OOM (rc=137); agent can still annotate "
            "but p_hat stays null. Raise instance memory / remove the cgroup cap."
        )
    return None
