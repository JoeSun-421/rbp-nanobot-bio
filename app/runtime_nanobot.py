# -*- coding: utf-8 -*-
"""Resolve the installed HKUDS nanobot package directory (runtime SoT target).

Prefer ``import nanobot`` (from ``pip install nanobot-ai``). Fall back to
``$NANOBOT_SRC`` / sibling clone for local development.

Never ``pip install nanobot`` — that is an unrelated PyPI package.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def resolve_nanobot_pkg_dir() -> Optional[Path]:
    """Return the directory that contains ``nanobot/__init__.py`` + ``agent/``."""
    try:
        import nanobot

        p = Path(getattr(nanobot, "__file__", "") or "").resolve()
        if p.is_file():
            return p.parent
    except Exception:
        pass
    return None


def resolve_nanobot_src(*, prefer_env: bool = True) -> Path:
    """Runtime root for overlay sync (package dir or sibling checkout).

    Default (product): prefer ``import nanobot`` / site-packages.
    Set ``NANOBOT_USE_CLONE=1`` to force sibling / ``NANOBOT_SRC`` checkout.
    """
    use_clone = os.environ.get("NANOBOT_USE_CLONE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    if not use_clone:
        pkg = resolve_nanobot_pkg_dir()
        if pkg is not None:
            return pkg

    if prefer_env:
        raw = os.environ.get("NANOBOT_SRC", "").strip()
        if raw:
            p = Path(raw).expanduser().resolve()
            if (p / "__init__.py").is_file() or (p / "nanobot.py").is_file():
                return p

    pkg = resolve_nanobot_pkg_dir()
    if pkg is not None:
        return pkg

    bio_root = Path(
        os.environ.get(
            "BIO_ROOT",
            Path(__file__).resolve().parents[2],
        )
    ).expanduser().resolve()
    sibling = bio_root / "nanobot"
    if (sibling / "__init__.py").is_file() or (sibling / "nanobot.py").is_file():
        return sibling

    raise FileNotFoundError(
        "HKUDS nanobot runtime not found. Install with:\n"
        "  pip install 'nanobot-ai>=0.2.2'\n"
        "Do NOT use `pip install nanobot` (unrelated robot-nav package).\n"
        "Dev alternative: clone https://github.com/HKUDS/nanobot and set "
        "NANOBOT_USE_CLONE=1 / NANOBOT_SRC."
    )


def ensure_nanobot_src_env() -> Path:
    """Set ``NANOBOT_SRC`` if unset; return resolved path."""
    path = resolve_nanobot_src()
    os.environ["NANOBOT_SRC"] = str(path)
    return path


def is_pip_install() -> bool:
    """True when import resolves under site-packages / dist-packages."""
    pkg = resolve_nanobot_pkg_dir()
    if pkg is None:
        return False
    s = str(pkg).replace("\\", "/")
    return "/site-packages/" in s or "/dist-packages/" in s


def describe() -> dict[str, str]:
    pkg = resolve_nanobot_pkg_dir()
    try:
        src = resolve_nanobot_src()
    except FileNotFoundError as e:
        return {"error": str(e)}
    ver = ""
    try:
        import nanobot as nb

        ver = getattr(nb, "__version__", "") or ""
    except Exception:
        pass
    return {
        "NANOBOT_SRC": str(src),
        "import_path": str(pkg) if pkg else "",
        "version": ver,
        "mode": "pip" if is_pip_install() else "source",
        "python": sys.executable,
    }
