#!/usr/bin/env python3
"""Assert proposal §6.2 overlay layout + sibling nanobot runtime import."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
        "rbp_eval/runner.py",
        "rbp_eval/evaluator.py",
        "rbp_eval/traces",
        "backends/delivery",
    ):
        if not (ROOT / rel).exists():
            fail(f"missing agent package path: {ROOT / rel}")

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

    print("OK: §6.2 overlay layout")
    print(f"  overlay={OVERLAY}")
    print(f"  runtime={runtime}")
    print(f"  import nanobot -> {nb_file}")


if __name__ == "__main__":
    main()
