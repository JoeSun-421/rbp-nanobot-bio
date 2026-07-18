# -*- coding: utf-8 -*-
"""LLM setup for the RNA–RBP agent.

Writes provider + API key + model into ``~/.nanobot/config.json`` using
nanobot's provider registry/schema — without nanobot's onboarding wizard.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG = Path(
    os.environ.get("NANOBOT_CONFIG", "~/.nanobot/config.json")
).expanduser()

FEATURED: tuple[tuple[str, str], ...] = (
    ("deepseek", "deepseek-chat"),
    ("openai", "gpt-4o-mini"),
    ("anthropic", "claude-3-5-sonnet-latest"),
    ("openrouter", "anthropic/claude-3.5-sonnet"),
    ("gemini", "gemini-1.5-flash"),
    ("dashscope", "qwen-plus"),
    ("zhipu", "glm-4-flash"),
    ("moonshot", "kimi-latest"),
    ("siliconflow", "deepseek-ai/DeepSeek-V3"),
)


def _display_name(name: str) -> str:
    try:
        from nanobot.providers.registry import find_by_name

        spec = find_by_name(name)
        if spec:
            return spec.label
    except Exception:
        pass
    return name.title()


def _needs_api_base(name: str) -> bool:
    return name == "custom"


def load_config() -> dict:
    """Read the existing config, or synthesize nanobot defaults if absent."""
    if DEFAULT_CONFIG.is_file():
        return json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    try:
        from nanobot.config.schema import Config

        return Config().model_dump(by_alias=True, mode="json")
    except Exception:
        return {"agents": {"defaults": {}}, "providers": {}}


def save_provider(
    *,
    provider: str,
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    path: Path = DEFAULT_CONFIG,
) -> Path:
    """Persist provider credentials + active model into the nanobot config."""
    cfg = load_config()
    cfg.setdefault("providers", {})
    block = dict(cfg["providers"].get(provider) or {})
    if api_key is not None:
        block["apiKey"] = api_key
    if api_base:
        block["apiBase"] = api_base
    cfg["providers"][provider] = block

    defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
    defaults["provider"] = provider
    defaults["model"] = model
    defaults.setdefault("botName", "RNA–RBP")
    defaults.setdefault("botIcon", "")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def current_summary(path: Path = DEFAULT_CONFIG) -> str:
    """One-line description of the active provider/model, keys redacted."""
    if not path.is_file():
        return "no config"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    d = (cfg.get("agents") or {}).get("defaults") or {}
    provider = d.get("provider") or "auto"
    model = d.get("model") or "?"
    block = (cfg.get("providers") or {}).get(provider) or {}
    keyed = "key set" if (block.get("apiKey") or block.get("api_key")) else "no key"
    return f"{provider} · {model} · {keyed}"


def _print_login_banner() -> None:
    try:
        from core.chat_ux import print_banner, Style
    except Exception:
        print("RNA–RBP Agent — LLM login", flush=True)
        return
    print_banner(
        "RNA–RBP Agent",
        "LLM login  ·  credentials → ~/.nanobot/config.json",
        stream=sys.stderr,
    )
    s = Style(sys.stderr)
    sys.stderr.write(
        s.dim("  Choose a provider, then enter model + API key (key is hidden).\n\n")
    )
    sys.stderr.flush()


def interactive_onboard(path: Path = DEFAULT_CONFIG) -> bool:
    """Arrow-key provider picker + hidden key entry. Falls back to plain input."""
    _print_login_banner()
    try:
        import questionary
        from questionary import Style as QStyle
    except Exception:
        return _plain_onboard(path)

    if not (os.isatty(0) and os.isatty(1)):
        return _plain_onboard(path)

    qstyle = QStyle(
        [
            ("qmark", "fg:cyan bold"),
            ("question", "bold"),
            ("answer", "fg:cyan"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:green"),
            ("separator", "fg:#6c6c6c"),
            ("instruction", "fg:#6c6c6c"),
            ("text", ""),
        ]
    )

    choices = [
        questionary.Choice(title=f"{_display_name(n):<14}  {dm}", value=(n, dm))
        for n, dm in FEATURED
    ]
    choices.append(
        questionary.Choice(
            title=f"{'Custom':<14}  OpenAI-compatible endpoint",
            value=("custom", ""),
        )
    )

    picked = questionary.select(
        "LLM provider",
        choices=choices,
        qmark="▸",
        style=qstyle,
        instruction="(↑/↓, Enter)",
    ).ask()
    if picked is None:
        return False
    provider, default_model = picked

    api_base = None
    if _needs_api_base(provider):
        api_base = questionary.text(
            "API base URL",
            qmark="▸",
            style=qstyle,
        ).ask()
        if not api_base:
            print("aborted: custom provider needs an API base URL")
            return False

    model = questionary.text(
        "Model",
        default=default_model,
        qmark="▸",
        style=qstyle,
    ).ask()
    if not model:
        print("aborted: model is required")
        return False

    api_key = questionary.password(
        "API key",
        qmark="▸",
        style=qstyle,
    ).ask()
    if api_key is None:
        return False

    save_provider(
        provider=provider,
        model=model.strip(),
        api_key=api_key.strip() or None,
        api_base=(api_base or "").strip() or None,
        path=path,
    )
    try:
        from core.chat_ux import Style

        s = Style(sys.stderr)
        sys.stderr.write(
            "\n"
            + s.green("✓ saved")
            + f"  {path}\n"
            + f"  {s.bold(provider)} · {model.strip()}\n"
            + s.dim("  Next:  rbp-agent chat\n\n")
        )
        sys.stderr.flush()
    except Exception:
        print(f"saved → {path}  [{provider} · {model.strip()}]")
    return True


def _plain_onboard(path: Path) -> bool:
    """Non-TTY fallback: numbered menu with plain prompts."""
    print("Select an LLM provider:")
    for i, (n, dm) in enumerate(FEATURED, 1):
        print(f"  {i}. {_display_name(n)}  ({dm})")
    print(f"  {len(FEATURED) + 1}. Custom (OpenAI-compatible)")
    raw = input("number › ").strip()
    try:
        idx = int(raw)
    except ValueError:
        print("aborted: not a number")
        return False
    if 1 <= idx <= len(FEATURED):
        provider, default_model = FEATURED[idx - 1]
        api_base = None
    elif idx == len(FEATURED) + 1:
        provider, default_model = "custom", ""
        api_base = input("API base URL › ").strip()
        if not api_base:
            print("aborted: custom needs an API base")
            return False
    else:
        print("aborted: out of range")
        return False

    model = input(f"model [{default_model}] › ").strip() or default_model
    if not model:
        print("aborted: model required")
        return False
    api_key = input("API key › ").strip()
    save_provider(
        provider=provider,
        model=model,
        api_key=api_key or None,
        api_base=api_base or None,
        path=path,
    )
    print(f"saved → {path}  [{provider} · {model}]")
    return True
