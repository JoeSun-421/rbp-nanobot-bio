#!/usr/bin/env python3
"""Sync proposal §6.2 SoT (tools + skill) into the installed nanobot runtime.

Source of truth (agent package)::
    nanobot-bio/nanobot/skills/rbp-agent/SKILL.md
    nanobot-bio/nanobot/agent/tools/rbp/*.py

Destination (runtime, default $BIO_ROOT/nanobot)::
    $NANOBOT_SRC/agent/tools/rbp/
    $NANOBOT_WORKSPACE/skills/rbp-agent/SKILL.md
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    bio = Path(os.environ.get("NANOBOT_BIO_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
    bio_root = Path(os.environ.get("BIO_ROOT", bio.parent)).expanduser().resolve()
    sot = bio / "nanobot"
    src_rbp = sot / "agent" / "tools" / "rbp"
    src_skill = sot / "skills" / "rbp-agent" / "SKILL.md"

    nanobot_src = Path(
        os.environ.get("NANOBOT_SRC", bio_root / "nanobot")
    ).expanduser().resolve()
    workspace = Path(
        os.environ.get("NANOBOT_WORKSPACE", bio / "workspace")
    ).expanduser().resolve()

    print(f"[install_rbp] SoT={sot}")
    print(f"[install_rbp] NANOBOT_SRC={nanobot_src}")
    print(f"[install_rbp] WORKSPACE={workspace}")

    if not src_rbp.is_dir():
        print("ERROR: missing §6.2 tools at", src_rbp, file=sys.stderr)
        return 1
    if not src_skill.is_file():
        print("ERROR: missing §6.2 skill at", src_skill, file=sys.stderr)
        return 1
    if not (nanobot_src / "__init__.py").is_file() and not (nanobot_src / "nanobot.py").is_file():
        print("ERROR: NANOBOT_SRC does not look like nanobot runtime:", nanobot_src, file=sys.stderr)
        return 1

    dst_rbp = nanobot_src / "agent" / "tools" / "rbp"
    dst_rbp.parent.mkdir(parents=True, exist_ok=True)
    if dst_rbp.exists():
        shutil.rmtree(dst_rbp)
    shutil.copytree(
        src_rbp,
        dst_rbp,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    print("[install_rbp] tools ->", dst_rbp)
    print("[install_rbp] tools:", sorted(p.name for p in dst_rbp.iterdir() if p.suffix == ".py"))

    dest_skill = workspace / "skills" / "rbp-agent" / "SKILL.md"
    dest_skill.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_skill, dest_skill)
    print("[install_rbp] skill ->", dest_skill)

    # Also keep a copy under runtime skills/ for frameworks that load from package tree
    runtime_skill = nanobot_src / "skills" / "rbp-agent" / "SKILL.md"
    runtime_skill.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_skill, runtime_skill)
    print("[install_rbp] skill (runtime) ->", runtime_skill)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
