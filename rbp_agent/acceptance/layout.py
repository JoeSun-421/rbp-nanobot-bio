#!/usr/bin/env python3
"""Assert plugin overlay layout + sibling nanobot runtime import."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIO_ROOT = ROOT.parent
OVERLAY = ROOT / "nanobot"

REQUIRED_TOOLS = [
    "predict.py",
    "catalogue.py",
    "seq.py",
    "structure.py",
    "annotation.py",
    "common.py",
    "register.py",
    "__init__.py",
]

FORBIDDEN_UNDER_OVERLAY = [
    "providers",
    "channels",
    "webui",
    "cli",
    "bus",
    "gateway",
    "cron",
    "session",
    "bridge",
    "apps",
    "api",
    "audio",
    "pairing",
    "security",
    "templates",
    "utils",
    "web",
    "sdk",
    "command",
    "config",
    "__init__.py",
    "nanobot.py",
    "pyproject.toml",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    skill = OVERLAY / "skills" / "rbp-agent" / "SKILL.md"
    if not skill.is_file():
        fail(f"missing {skill}")

    tools = OVERLAY / "agent" / "tools" / "rbp"
    missing = [n for n in REQUIRED_TOOLS if not (tools / n).is_file()]
    if missing:
        fail(f"missing tools under {tools}: {missing}")

    for name in FORBIDDEN_UNDER_OVERLAY:
        p = OVERLAY / name
        if p.exists():
            fail(f"overlay must not contain framework path: {p}")

    for rel in (
        "nanobot/skills/rbp-agent/SKILL.md",
        "nanobot/agent/tools/rbp/predict.py",
        "nanobot/agent/tools/rbp/catalogue.py",
        "nanobot/agent/tools/rbp/seq.py",
        "nanobot/agent/tools/rbp/structure.py",
        "nanobot/agent/tools/rbp/annotation.py",
        "nanobot/agent/tools/rbp/common.py",
        "rbp_eval/runner.py",
        "rbp_eval/evaluator.py",
        "rbp_eval/fuse_hits.py",
        "rbp_eval/proxy_cache.py",
        "rbp_eval/nanobot_hooks.py",
        "rbp_eval/hooks.py",
        "rbp_agent/core/paths.py",
        "rbp_agent/cli.py",
        "rbp_agent/backends/delivery",
        "artifacts",
    ):
        if not (ROOT / rel).exists():
            fail(f"missing SoT/agent path: {ROOT / rel}")

    # Eval lives at top-level rbp_eval/, not under rbp_agent/
    if (ROOT / "rbp_agent" / "eval").exists():
        fail("rbp_agent/eval must not exist — use top-level rbp_eval/")
    if (ROOT / "rbp_agent" / "_proposal_sot").exists():
        fail("rbp_agent/_proposal_sot removed — SoT is repo-root nanobot/ only")
    if (ROOT / "rbp_eval" / "fusion.py").exists():
        fail("rbp_eval/fusion.py removed — import rbp_eval.fuse_hits")

    # Reject dead shims that re-export deleted rbp_agent.eval
    for name in ("fuse_hits.py", "proxy_cache.py", "nanobot_hooks.py", "hooks.py"):
        text = (ROOT / "rbp_eval" / name).read_text(encoding="utf-8", errors="replace")
        if "from rbp_agent.eval" in text:
            fail(f"rbp_eval/{name} is a broken shim to rbp_agent.eval")

    runtime = Path(os.environ.get("NANOBOT_SRC", BIO_ROOT / "nanobot")).expanduser().resolve()
    if not (runtime / "__init__.py").is_file() and not (runtime / "nanobot.py").is_file():
        fail(f"sibling runtime missing at {runtime}")

    # Prefer BIO_ROOT so flat-layout sibling wins over any accidental overlay
    bio_s = str(BIO_ROOT)
    while bio_s in sys.path:
        sys.path.remove(bio_s)
    sys.path.insert(0, bio_s)
    # Drop overlay parent if present ahead of BIO_ROOT
    root_s = str(ROOT)
    while root_s in sys.path:
        sys.path.remove(root_s)

    nb = importlib.import_module("nanobot")
    nb_file = Path(getattr(nb, "__file__", "") or "").resolve()
    nb_s = str(nb_file).replace("\\", "/")
    if "/nanobot-bio/" in nb_s:
        fail(f"import nanobot shadowed by overlay: {nb_file}")

    print("OK: plugin overlay layout")
    print(f"  overlay={OVERLAY}")
    print(f"  runtime={runtime}")
    print(f"  import nanobot -> {nb_file}")


if __name__ == "__main__":
    main()
