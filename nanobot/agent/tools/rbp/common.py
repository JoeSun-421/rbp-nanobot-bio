# -*- coding: utf-8 -*-
"""
Shared helpers for RBP tools (proposal §5–§6.2).

Path (source of truth)::
    nanobot-bio/nanobot/agent/tools/rbp/common.py

Delivery science is NOT reimplemented — bridged via DeliveryToolClient.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional


def ensure_nanobot_bio_on_path() -> Path:
    """Locate nanobot-bio root (backends/delivery) and put it on sys.path."""
    env = os.environ.get("NANOBOT_BIO_ROOT")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    # .../nanobot-bio/nanobot/agent/tools/rbp/common.py → package root = nanobot-bio
    if len(here.parents) > 4:
        candidates.append(here.parents[4])
    if len(here.parents) > 3:
        nb_pkg = here.parents[3]  # .../nanobot-bio/nanobot
        candidates.append(nb_pkg.parent)  # nanobot-bio
        candidates.append(nb_pkg.parent.parent / "nanobot-bio")
    bio = os.environ.get("BIO_ROOT")
    if bio:
        candidates.append(Path(bio) / "nanobot-bio")
        candidates.append(Path(bio))

    for c in candidates:
        try:
            c = c.resolve()
        except OSError:
            continue
        if (c / "backends" / "delivery" / "client.py").is_file():
            if str(c) not in sys.path:
                sys.path.append(str(c))
            os.environ.setdefault("NANOBOT_BIO_ROOT", str(c))
            return c
    raise FileNotFoundError(
        "Cannot find nanobot-bio (backends/delivery). "
        "Set NANOBOT_BIO_ROOT=/path/to/nanobot-bio"
    )


def get_delivery_client(
    *,
    offline: bool = False,
    device: Optional[str] = None,
    use_conda: bool = True,
):
    ensure_nanobot_bio_on_path()
    from backends.delivery.client import DeliveryToolClient
    from backends.delivery.env import apply_delivery_env

    apply_delivery_env()
    return DeliveryToolClient(
        offline=offline,
        device=device or os.environ.get("RHOBIND_DEVICE", "cpu"),
        use_conda=use_conda,
    )


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def ok(value: Any, latency_ms: float = 0.0) -> dict[str, Any]:
    return {"status": "ok", "value": value, "latency_ms": round(float(latency_ms), 3)}


def err(reason: str, latency_ms: float = 0.0) -> dict[str, Any]:
    return {"status": "error", "reason": str(reason), "latency_ms": round(float(latency_ms), 3)}


def timed_call(fn):
    t0 = time.perf_counter()
    try:
        v = fn()
        return v, (time.perf_counter() - t0) * 1000.0, None
    except Exception as e:  # noqa: BLE001
        return None, (time.perf_counter() - t0) * 1000.0, f"{type(e).__name__}: {e}"
