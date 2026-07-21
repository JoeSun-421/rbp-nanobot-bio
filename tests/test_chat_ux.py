# -*- coding: utf-8 -*-
"""Chat UX helpers (product CLI chrome)."""

from __future__ import annotations

from rbp_agent.core.chat_ux import (
    CHAT_HELP,
    ThinkingSpinner,
    _color_label,
    _peek_verdict_label,
    print_chat_header,
    print_status_panel,
    print_turn_footer,
    print_verdict_block,
)


def test_help_lists_core_commands():
    for cmd in ("/help", "/status", "/tools", "/quit", "/thinking"):
        assert cmd in CHAT_HELP


def test_verdict_label_peek_and_color():
    body = '{\n  "label": "Strong",\n  "p_hat": 0.9\n}'
    assert _peek_verdict_label(body) == "Strong"
    from rbp_agent.core.chat_ux import Style
    import io

    s = Style(io.StringIO())
    s.on = False
    assert "Strong" in _color_label("Strong", s)


def test_spinner_status_phases():
    sp = ThinkingSpinner(bot_name="rbp-agent")
    sp._enabled = False
    sp._inner = None
    sp.update("thinking")
    t1 = sp._status_text()
    assert "Thinking" in t1 or "…" in t1 or "s" in t1
    sp.update("seq_similarity")
    t2 = sp._status_text()
    assert "seq_similarity" in t2


def test_print_chrome_no_crash(capsys):
    print_chat_header(
        llm_summary="deepseek / test",
        n_tools=12,
        skill_ok=True,
        session_key="chat-test",
    )
    print_status_panel(
        llm_summary="deepseek / test",
        n_tools=12,
        session_key="chat-test",
        skill_ok=True,
    )
    print_verdict_block('{"label":"Likely","p_hat":0.6,"confidence":"low"}')
    print_turn_footer(elapsed_s=1.23, mode="nanobot_llm", n_tools=3)
