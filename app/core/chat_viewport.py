# -*- coding: utf-8 -*-
"""Fixed-viewport chat TUI (prompt_toolkit).

Patterns drawn from mature agent CLIs (Claude Code, OpenCode, Aider, Gemini CLI,
Codex CLI, Crush, OpenHands): scrollable transcript above a sticky input bar,
role-colored thinking / tools / results, PageUp/PageDown history navigation.
Falls back cleanly when not a TTY or prompt_toolkit Application fails.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence


# prompt_toolkit style names → ANSI roles (Claude Code / OpenCode-like)
STYLE_USER = "class:role.user"
STYLE_THINK = "class:role.think"
STYLE_TOOL = "class:role.tool"
STYLE_TOOL_OK = "class:role.tool_ok"
STYLE_TOOL_ERR = "class:role.tool_err"
STYLE_STEP = "class:role.step"
STYLE_VERDICT = "class:role.verdict"
STYLE_DIM = "class:role.dim"
STYLE_SYS = "class:role.sys"


@dataclass
class TranscriptLine:
    style: str
    text: str


@dataclass
class TranscriptStore:
    """In-memory conversation buffer (scrollable in the viewport)."""

    lines: list[TranscriptLine] = field(default_factory=list)
    max_lines: int = 4000

    def append(self, style: str, text: str) -> None:
        for raw in (text or "").splitlines() or [""]:
            self.lines.append(TranscriptLine(style=style, text=raw))
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines :]

    def extend_block(self, style: str, text: str) -> None:
        self.append(style, text)

    def clear(self) -> None:
        self.lines.clear()

    def as_formatted_text(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for ln in self.lines:
            out.append((ln.style, ln.text + "\n"))
        return out


class TranscriptSink:
    """Dual sink: viewport store + optional live stderr (for non-TUI / debug)."""

    def __init__(
        self,
        store: TranscriptStore,
        *,
        live: bool = False,
        stream: Any = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self.store = store
        self.live = live
        self.stream = stream or sys.stderr
        self.on_change = on_change

    def _emit(self, style: str, text: str, *, ansi: str = "") -> None:
        self.store.append(style, text)
        if self.live and self.stream is not None:
            self.stream.write((ansi or text) + "\n")
            self.stream.flush()
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    def sys(self, text: str) -> None:
        self._emit(STYLE_SYS, text)

    def dim(self, text: str) -> None:
        self._emit(STYLE_DIM, text)

    def user(self, text: str) -> None:
        self._emit(STYLE_USER, f"You  {text}")

    def thinking(self, text: str) -> None:
        for ln in (text or "").splitlines() or [""]:
            self._emit(STYLE_THINK, f"  · {ln}" if ln else "  ·")

    def step(self, text: str) -> None:
        self._emit(STYLE_STEP, text)

    def tool_call(self, name: str, args: str = "") -> None:
        head = f"  ▸ TOOL  {name}"
        self._emit(STYLE_TOOL, head + (f"  {args}" if args else ""))

    def tool_ok(self, name: str, summary: str) -> None:
        self._emit(STYLE_TOOL_OK, f"  ✓ {name}  {summary}")

    def tool_err(self, name: str, summary: str) -> None:
        self._emit(STYLE_TOOL_ERR, f"  ✗ {name}  {summary}")

    def verdict(self, text: str) -> None:
        self._emit(STYLE_VERDICT, text)


def _chat_style() -> Any:
    from prompt_toolkit.styles import Style

    return Style.from_dict(
        {
            "role.user": "bold ansicyan",
            "role.think": "ansimagenta italic",
            "role.tool": "boldansiyellow",
            "role.tool_ok": "ansigreen",
            "role.tool_err": "bold ansired",
            "role.step": "ansibrightblack",
            "role.verdict": "bold ansicyan",
            "role.dim": "ansibrightblack",
            "role.sys": "ansibrightblue",
            "status": "reverse ansibrightblack",
            "input-prompt": "bold ansicyan",
            "frame.label": "ansicyan",
        }
    )


def tui_available() -> bool:
    if os.environ.get("RBP_CHAT_TUI", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    if os.environ.get("NO_COLOR") or os.environ.get("RBP_NO_COLOR"):
        # Still allow TUI; colors just degrade
        pass
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    try:
        import prompt_toolkit  # noqa: F401
    except ImportError:
        return False
    return True


class ChatViewport:
    """Fullscreen chat: scrollable transcript + sticky You: input (OpenCode-like)."""

    def __init__(
        self,
        *,
        bot_name: str = "nanobot-bio",
        bot_icon: str = "◈",
        title: str = "",
    ) -> None:
        self.bot_name = bot_name
        self.bot_icon = bot_icon
        self.title = title or f"{bot_icon} {bot_name}".strip()
        self.store = TranscriptStore()
        self.sink = TranscriptSink(self.store, live=False, on_change=self._invalidate)
        self._status = "PgUp/PgDn scroll · Enter send · /help · Ctrl+C quit"
        self._app: Any = None
        self._kb: Any = None
        self._input_buf: Any = None
        self._submitted: Optional[str] = None
        self._should_exit = False
        self._busy = False

    def _invalidate(self) -> None:
        if self._app is not None:
            try:
                self._app.invalidate()
            except Exception:
                pass

    def set_status(self, text: str) -> None:
        self._status = text
        self._invalidate()

    def set_busy(self, busy: bool, status: str = "") -> None:
        self._busy = busy
        if status:
            self._status = status
        elif busy:
            self._status = f"{self.bot_name} is working…  (scroll with PgUp/PgDn)"
        else:
            self._status = "PgUp/PgDn scroll · Enter send · /help · Ctrl+C quit"
        self._invalidate()

    def _build_app(self) -> Any:
        from prompt_toolkit.application import Application
        from prompt_toolkit.buffer import Buffer
        from prompt_toolkit.document import Document
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Dimension, HSplit, Layout, Window
        from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
        from prompt_toolkit.layout.margins import ScrollbarMargin
        from prompt_toolkit.layout.scrollable_pane import ScrollablePane
        from prompt_toolkit.widgets import Frame

        store = self.store

        def get_transcript() -> Sequence[tuple[str, str]]:
            body = store.as_formatted_text()
            if not body:
                return [(STYLE_DIM, "  (conversation will appear here)\n")]
            return body

        def get_status() -> str:
            return f" {self._status} "

        kb = KeyBindings()
        self._kb = kb

        @kb.add("c-c")
        @kb.add("c-d")
        def _quit(event) -> None:  # type: ignore[no-untyped-def]
            self._should_exit = True
            self._submitted = None
            event.app.exit()

        @kb.add("escape", "enter")
        def _newline(event) -> None:  # type: ignore[no-untyped-def]
            event.current_buffer.insert_text("\n")

        @Condition
        def not_busy() -> bool:
            return not self._busy

        input_buf = Buffer(
            name="input",
            multiline=False,
            read_only=Condition(lambda: self._busy),
        )
        self._input_buf = input_buf

        @kb.add("enter", filter=not_busy)
        def _submit(event) -> None:  # type: ignore[no-untyped-def]
            text = input_buf.text
            input_buf.document = Document()
            self._submitted = text
            event.app.exit()

        transcript_window = Window(
            content=FormattedTextControl(get_transcript, focusable=False),
            wrap_lines=True,
            always_hide_cursor=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        # ScrollablePane gives mouse / key scroll over long histories
        scroll_body = ScrollablePane(
            transcript_window,
            show_scrollbar=True,
            keep_cursor_visible=False,
        )

        status_bar = Window(
            content=FormattedTextControl(get_status, style="class:status"),
            height=1,
        )
        prompt_label = Window(
            content=FormattedTextControl(
                lambda: [("class:input-prompt", "You: ")],
            ),
            width=5,
            dont_extend_width=True,
        )
        input_window = Window(
            BufferControl(buffer=input_buf, focus_on_click=True),
            height=Dimension(min=1, preferred=1, max=4),
        )

        from prompt_toolkit.layout.containers import VSplit

        root = HSplit(
            [
                Frame(
                    scroll_body,
                    title=self.title,
                    style="class:frame",
                ),
                status_bar,
                VSplit([prompt_label, input_window]),
            ]
        )

        # Scroll keys when input focused — scroll the pane via key bindings
        @kb.add("pageup")
        def _pgup(event) -> None:  # type: ignore[no-untyped-def]
            event.app.layout.current_window = transcript_window
            # Fall through: ScrollablePane responds to pageup when focused
            event.app.layout.focus(input_buf)

        # Attach pageup/pagedown to scrollable via vertical_scroll on window
        tw = transcript_window

        @kb.add("pageup")
        def _scroll_up(event) -> None:  # type: ignore[no-untyped-def]
            tw.vertical_scroll = max(0, tw.vertical_scroll - 10)

        @kb.add("pagedown")
        def _scroll_down(event) -> None:  # type: ignore[no-untyped-def]
            tw.vertical_scroll += 10

        @kb.add("c-up")
        def _line_up(event) -> None:  # type: ignore[no-untyped-def]
            tw.vertical_scroll = max(0, tw.vertical_scroll - 1)

        @kb.add("c-down")
        def _line_down(event) -> None:  # type: ignore[no-untyped-def]
            tw.vertical_scroll += 1

        app = Application(
            layout=Layout(root, focused_element=input_buf),
            key_bindings=kb,
            style=_chat_style(),
            full_screen=True,
            mouse_support=True,
        )
        self._app = app
        return app

    def prompt(self) -> Optional[str]:
        """Block until the user submits a line; None = quit."""
        self._submitted = None
        self._should_exit = False
        self.set_busy(False)
        try:
            app = self._build_app()
            # Auto-scroll to bottom on open
            app.run()
        except (EOFError, KeyboardInterrupt):
            return None
        except Exception:
            return None
        if self._should_exit:
            return None
        return self._submitted

    def dump_plain(self) -> str:
        return "\n".join(ln.text for ln in self.store.lines)
