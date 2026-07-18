# -*- coding: utf-8 -*-
"""RBPAgent: register delivery tools on Nanobot and run the LLM agent loop."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Union

_ROOT = Path(__file__).resolve().parent
_default_nb = _ROOT / "nanobot"
_ns = os.environ.get("NANOBOT_SRC") or (str(_default_nb) if _default_nb.is_dir() else "")
if _ns:
    _nb_parent = str(Path(_ns).expanduser().resolve().parent)
    while _nb_parent in sys.path:
        sys.path.remove(_nb_parent)
    sys.path.insert(0, _nb_parent)
else:
    _bio = str(_ROOT.parent)
    while _bio in sys.path:
        sys.path.remove(_bio)
    sys.path.insert(0, _bio)
_root_s = str(_ROOT)
if _root_s not in sys.path:
    sys.path.insert(0, _root_s)

os.environ.setdefault("NANOBOT_BIO_ROOT", str(_ROOT))
os.environ.setdefault(
    "NANOBOT_SRC", str(_default_nb if _default_nb.is_dir() else _ROOT / "nanobot")
)

from backends.delivery.client import DeliveryToolClient
from backends.delivery.env import apply_delivery_env
from core.verdict_schema import extract_verdict_from_content, validate_verdict

PACKAGE_ROOT = _ROOT
WORKSPACE = PACKAGE_ROOT / "workspace"
DEFAULT_TRACE = PACKAGE_ROOT / "rbp_eval" / "traces" / "nanobot_run.jsonl"

_SKILL_CANDIDATES = (
    PACKAGE_ROOT / "nanobot" / "skills" / "rbp-agent" / "SKILL.md",
    PACKAGE_ROOT / "workspace" / "skills" / "rbp-agent" / "SKILL.md",
)


# ---------------------------------------------------------------------------
# Install / skill
# ---------------------------------------------------------------------------

def install_rbp_tools_into_nanobot() -> Path:
    """Ensure workspace skill is synced; tools live under nested nanobot/."""
    import runpy

    runpy.run_path(str(PACKAGE_ROOT / "scripts" / "install_rbp_into_nanobot.py"))
    return Path(os.environ.get("NANOBOT_SRC", PACKAGE_ROOT / "nanobot")) / "agent" / "tools" / "rbp"


_AGENTS_BOOTSTRAP = """# RNA–RBP agent

You predict RNA–RBP interactions using delivery tools only.

## Stage 0 (mandatory when RBP is in catalogue)

1. `resolve_rbp` → if `in_panel=true`, call `predict_interaction` **once** with that alias (own head).
2. Map `predictions[0].prob` → `p_hat` / label; emit **JSON only**; **stop**.
3. Do **not** call transfer / seq_similarity / domain / literature for in-panel targets.

Golden: delivery `agent/examples/sample_rna_pos.txt` × PTBP1 → own-head ≈ 0.966.

Unseen RBPs: retrieve → predict donor heads → integrate (BUILD_SPEC §4).
Never invent `p_hat`. Never pass RNA into protein-only tools.
"""


def ensure_workspace_skill(workspace: Optional[Path] = None) -> Path:
    """Skill + AGENTS.md under nanobot workspace (always-on Stage 0 rules)."""
    ws = Path(workspace or WORKSPACE)
    dest = ws / "skills" / "rbp-agent" / "SKILL.md"
    for src in _SKILL_CANDIDATES:
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            break
    agents = ws / "AGENTS.md"
    agents.parent.mkdir(parents=True, exist_ok=True)
    # Keep our Stage-0 contract at the top; preserve any extra user notes below a marker.
    marker = "\n<!-- user-notes -->\n"
    extra = ""
    if agents.is_file():
        old = agents.read_text(encoding="utf-8")
        if marker in old:
            extra = old.split(marker, 1)[1]
        elif not old.strip().startswith("# RNA–RBP agent"):
            extra = old
    agents.write_text(_AGENTS_BOOTSTRAP + marker + extra, encoding="utf-8")
    return dest


def skill_path() -> Optional[Path]:
    for p in _SKILL_CANDIDATES:
        if p.is_file():
            return p
    return None


def _register_tools(registry) -> list[str]:
    """Register proposal P0–P2 + Stage whitelist extras (not full delivery surface)."""
    try:
        from nanobot.agent.tools.rbp.register import register_rbp_tools

        _reg, names = register_rbp_tools(registry, include_raw_delivery="whitelist")
        # Guard: empty ToolRegistry is falsy (has __len__); ensure tools land on caller registry
        if _reg is not registry and registry is not None:
            for n in names:
                t = _reg.get(n)
                if t is not None and registry.get(n) is None:
                    registry.register(t)
        return names
    except ImportError:
        pass

    # Try install then import
    try:
        install_rbp_tools_into_nanobot()
        from nanobot.agent.tools.rbp.register import register_rbp_tools

        _reg, names = register_rbp_tools(registry, include_raw_delivery="whitelist")
        if _reg is not registry and registry is not None:
            for n in names:
                t = _reg.get(n)
                if t is not None and registry.get(n) is None:
                    registry.register(t)
        return names
    except Exception:
        pass

    # Fallback: delivery registry (requires real nanobot Tool base)
    from backends.delivery.registry import register_tools

    return register_tools(registry, include_raw_delivery="whitelist")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class AgentResult:
    def __init__(
        self,
        content: str,
        *,
        mode: str,
        session_key: str,
        tool_names: list[str],
        verdict: Optional[dict[str, Any]] = None,
        traces: Optional[list[dict[str, Any]]] = None,
        error: Optional[str] = None,
        linux_notes: Optional[list[str]] = None,
        mvp_complete: bool = False,
        verdict_valid: bool = False,
        verdict_errors: Optional[list[str]] = None,
    ):
        self.content = content
        self.mode = mode  # nanobot_llm | error (| fixture_pipeline if explicitly requested)
        self.session_key = session_key
        self.tool_names = tool_names
        self.verdict = verdict or {}
        self.traces = traces or []
        self.error = error
        self.linux_notes = linux_notes or []
        self.mvp_complete = mvp_complete
        self.verdict_valid = verdict_valid
        self.verdict_errors = verdict_errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "session_key": self.session_key,
            "mvp_complete": self.mvp_complete,
            "verdict_valid": self.verdict_valid,
            "verdict_errors": self.verdict_errors,
            "verdict": self.verdict,
            "error": self.error,
            "n_tools": len(self.tool_names),
            "n_traces": len(self.traces),
            "linux_notes": self.linux_notes,
            "content": self.content,
        }


# ---------------------------------------------------------------------------
# RBPAgent
# ---------------------------------------------------------------------------

class RBPAgent:
    """Nanobot controller + RBP delivery tools. No fixed pipeline fallback."""

    def __init__(
        self,
        *,
        offline: bool = False,
        device: str = "cpu",
        use_conda: bool = True,
        workspace: Optional[Union[str, Path]] = None,
        config_path: Optional[Union[str, Path]] = None,
        hooks: Optional[list] = None,
        auto_install_into_nanobot: bool = True,
        prefer_nanobot_llm: bool = True,
        allow_fallback: bool = False,  # kept for API compat; ignored (always False)
    ):
        apply_delivery_env()
        self.workspace = Path(workspace or WORKSPACE)
        self.config_path = Path(config_path).expanduser() if config_path else None
        ensure_workspace_skill(self.workspace)
        self.client = DeliveryToolClient(
            offline=offline, device=device, use_conda=use_conda
        )
        self.hooks = list(hooks or [])
        self.device = device
        self.offline = offline
        self.prefer_nanobot_llm = prefer_nanobot_llm
        self.allow_fallback = False
        if allow_fallback:
            # core/pipeline removed — product path is Nanobot.run only
            pass

        if auto_install_into_nanobot:
            try:
                install_rbp_tools_into_nanobot()
            except Exception as e:
                if os.environ.get("RBP_DEBUG"):
                    print(f"[RBPAgent] install into nanobot (optional): {e}")

        self.registry = None
        self.tool_names: list[str] = []
        self._init_registry()

    def _init_registry(self) -> None:
        try:
            from nanobot.agent.tools.registry import ToolRegistry

            self.registry = ToolRegistry()
            self.tool_names = _register_tools(self.registry)
        except ImportError as e:
            self.registry = None
            self.tool_names = []
            print(f"[RBPAgent] nanobot not importable ({e}); tool registration deferred.")

    # ----- nanobot wiring -----

    def tool_schemas(self) -> list[dict[str, Any]]:
        if self.registry is None:
            return []
        return self.registry.get_definitions()

    def inject_into_nanobot(self, bot: Any) -> list[str]:
        """Register all RBP/delivery tools on live Nanobot AgentLoop.tools."""
        if self.registry is None:
            self._init_registry()
        if self.registry is None:
            raise RuntimeError("nanobot ToolRegistry unavailable; install nanobot first")
        loop = getattr(bot, "_loop", None)
        if loop is None or not hasattr(loop, "tools"):
            raise TypeError("Expected Nanobot instance with _loop.tools")
        # Drop shell/network defaults that derail RNA–RBP evaluation (LLM may pip install).
        for noisy in (
            "exec",
            "spawn",
            "write_stdin",
            "list_exec_sessions",
            "run_cli_app",
            "web_search",
            "web_fetch",
            "long_task",
            "apply_patch",
            "edit_file",
            "write_file",
            "find_files",
            "grep",
            "list_dir",
            "read_file",
        ):
            try:
                loop.tools.unregister(noisy)
            except Exception:
                pass
        names = []
        for name in self.tool_names:
            t = self.registry.get(name)
            if t is not None:
                loop.tools.register(t)
                names.append(name)
        active = sorted(loop.tools._tools.keys())
        if os.environ.get("RBP_DEBUG"):
            print(f"[RBPAgent] tools after inject ({len(active)}): {active}")
        return names

    def build_nanobot(self) -> Any:
        from nanobot import Nanobot

        ensure_workspace_skill(self.workspace)
        kwargs: dict[str, Any] = {"workspace": self.workspace}
        if self.config_path is not None:
            kwargs["config_path"] = self.config_path
        bot = Nanobot.from_config(**kwargs)
        self.inject_into_nanobot(bot)
        self._bot = bot
        return bot

    def get_nanobot(self) -> Any:
        bot = getattr(self, "_bot", None)
        if bot is None:
            bot = self.build_nanobot()
        return bot

    async def run(
        self,
        message: str,
        *,
        session_key: str = "rbp:default",
        force_fallback: bool = False,
        fallback_kwargs: Optional[dict[str, Any]] = None,
        trace_path: Optional[Union[str, Path]] = None,
        extra_hooks: Optional[list[Any]] = None,
    ) -> AgentResult:
        """Run Nanobot LLM agent (proposal primary path). No pipeline fallback."""
        notes = linux_feasibility_notes()
        if force_fallback or fallback_kwargs:
            err = (
                "core/pipeline was removed. Product path is Nanobot.run only. "
                "Use rbp-agent agent|chat|own-head."
            )
            return AgentResult(
                content=json.dumps({"error": err}, ensure_ascii=False),
                mode="error",
                session_key=session_key,
                tool_names=list(self.tool_names),
                error=err,
                linux_notes=notes,
                mvp_complete=False,
            )

        tp = Path(trace_path or DEFAULT_TRACE)
        tp.parent.mkdir(parents=True, exist_ok=True)
        trace_hook = _make_trace_hook(tp, session_key)
        hooks = [trace_hook, *self.hooks, *(extra_hooks or [])]

        if self.offline or not self.prefer_nanobot_llm:
            err = (
                "Agent path requires Nanobot LLM "
                "(offline/prefer_nanobot_llm=False unsupported)"
            )
            return AgentResult(
                content=json.dumps({"error": err}, ensure_ascii=False),
                mode="error",
                session_key=session_key,
                tool_names=list(self.tool_names),
                error=err,
                linux_notes=notes,
                mvp_complete=False,
            )

        try:
            bot = self.get_nanobot()
            result = await bot.run(
                message,
                session_key=session_key,
                hooks=hooks,
            )
            content = getattr(result, "content", None) or str(result)
            verdict = extract_verdict_from_content(content)
            ok_v, verrs = validate_verdict(verdict)
            return AgentResult(
                content=content,
                mode="nanobot_llm",
                session_key=session_key,
                tool_names=list(self.tool_names),
                verdict=verdict,
                traces=list(getattr(trace_hook, "_buffer", [])),
                linux_notes=notes,
                mvp_complete=ok_v,
                verdict_valid=ok_v,
                verdict_errors=verrs,
            )
        except Exception as e:
            fb_err = f"{type(e).__name__}: {e}"
            notes = notes + [
                f"Nanobot.run failed: {fb_err}",
                "Fix: rbp-agent onboard + LLM API; ensure nested nanobot imports.",
            ]
            if hasattr(trace_hook, "push_event"):
                trace_hook.push_event({"type": "nanobot_run_failed", "error": fb_err})
            return AgentResult(
                content=json.dumps(
                    {"error": fb_err, "mode": "error"},
                    ensure_ascii=False,
                ),
                mode="error",
                session_key=session_key,
                tool_names=list(self.tool_names),
                error=fb_err,
                linux_notes=notes,
                mvp_complete=False,
            )

    def run_sync(self, message: str, **kwargs: Any) -> AgentResult:
        """Sync wrapper; accepts the same kwargs as ``run`` (incl. extra_hooks)."""
        return asyncio.run(self.run(message, **kwargs))


def linux_feasibility_notes() -> list[str]:
    return [
        "Agent path: Nanobot.run + RBP tools → delivery (RhoBind needs rhobind conda + RAM/GPU).",
        "LLM config: rbp-agent onboard",
        "Portable roots: BIO_ROOT, DELIVERY_ROOT, AGENT_DB, NANOBOT_CONFIG",
    ]


def _make_trace_hook(path: Path, session_key: str):
    try:
        from rbp_eval.nanobot_hooks import RBPTraceHook

        return RBPTraceHook(path, session_key=session_key)
    except ImportError:
        from rbp_eval.hooks import JsonlTraceHook

        return JsonlTraceHook(path, session_key=session_key)
