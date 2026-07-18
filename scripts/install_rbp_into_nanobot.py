#!/usr/bin/env python3
"""Sync skill SoT → workspace (tools already live under nested nanobot/)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    bio = Path(os.environ.get("NANOBOT_BIO_ROOT", Path(__file__).resolve().parents[1]))
    nanobot_src = Path(os.environ.get("NANOBOT_SRC", bio / "nanobot")).expanduser().resolve()
    workspace = Path(os.environ.get("NANOBOT_WORKSPACE", bio / "workspace"))

    dst_rbp = nanobot_src / "agent" / "tools" / "rbp"
    src_skill = nanobot_src / "skills" / "rbp-agent" / "SKILL.md"

    print(f"[install_rbp] NANOBOT_SRC={nanobot_src}")
    if not dst_rbp.is_dir():
        print("ERROR: missing tools at", dst_rbp, file=sys.stderr)
        return 1
    if not src_skill.is_file():
        print("ERROR: missing skill at", src_skill, file=sys.stderr)
        return 1

    dest = workspace / "skills" / "rbp-agent" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_skill, dest)
    print("[install_rbp] skill ->", dest)
    print("[install_rbp] tools:", sorted(p.name for p in dst_rbp.iterdir() if p.suffix == ".py"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
