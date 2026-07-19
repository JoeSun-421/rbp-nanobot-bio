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


_CUDA_CACHE: Optional[bool] = None


def _nvidia_visible() -> bool:
    """Fast GPU probe without importing torch (chat startup path)."""
    if os.path.exists("/dev/nvidia0"):
        return True
    try:
        import shutil
        import subprocess

        if not shutil.which("nvidia-smi"):
            return False
        r = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0 and bool((r.stdout or b"").strip())
    except Exception:
        return False


def cuda_available(*, force_refresh: bool = False, allow_torch: bool = False) -> bool:
    """True when a CUDA device is visible (ideal GPU env for RhoBind / ESM).

    Prefer ``nvidia-smi`` / ``/dev/nvidia0`` so agent startup does not pay for
    ``import torch`` (~1.5s). Torch is only used when ``allow_torch=True`` and
    the fast probe is inconclusive.

    Result is cached for the process. Set ``RHOBIND_FORCE_CPU=1`` in tests.
    """
    global _CUDA_CACHE
    if os.environ.get("RHOBIND_FORCE_CPU", "").strip().lower() in ("1", "true", "yes"):
        return False
    if _CUDA_CACHE is not None and not force_refresh:
        return _CUDA_CACHE

    ok = _nvidia_visible()
    if not ok and allow_torch:
        try:
            import torch  # type: ignore

            ok = bool(torch.cuda.is_available())
        except Exception:
            ok = False

    _CUDA_CACHE = ok
    return ok


def resolve_device(requested: Optional[str] = None) -> str:
    """Resolve compute device for delivery tools.

    Ideal product default is **CUDA when available** (HANDOFF / BUILD_SPEC).
    Accepted values: ``auto`` | ``cuda`` | ``cpu`` | empty (→ env / auto).

    Does **not** import torch on the hot path (chat / RBPAgent init).
    """
    raw = (requested if requested is not None else os.environ.get("RHOBIND_DEVICE", "auto"))
    raw = str(raw or "auto").strip().lower()
    if raw in ("cuda", "gpu"):
        return "cuda"
    if raw == "cpu":
        return "cpu"
    if raw in ("", "auto", "default"):
        return "cuda" if cuda_available(allow_torch=False) else "cpu"
    # Unknown token — still prefer CUDA in ideal envs.
    return "cuda" if cuda_available(allow_torch=False) else "cpu"


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
        device=resolve_device(device),
        use_conda=use_conda,
    )


def catalogue_fasta_path() -> Optional[Path]:
    """Bundled all_rbps.fasta under delivery reference/ (read-only)."""
    roots: list[Path] = []
    for key in ("RBP_PROTEINS", "DELIVERY_ROOT", "BUNDLE_ROOT"):
        v = os.environ.get(key)
        if v:
            roots.append(Path(v))
    dr = os.environ.get("DELIVERY_ROOT")
    if dr:
        roots.append(Path(dr) / "reference")
    for r in roots:
        for cand in (
            r / "sequences" / "all_rbps.fasta",
            r / "reference" / "sequences" / "all_rbps.fasta",
        ):
            if cand.is_file():
                return cand
    return None


def load_catalogue_sequence(query: str) -> Optional[str]:
    """Load protein sequence for alias/UniProt from delivery ``all_rbps.fasta``.

    Headers look like ``>YTHDF2|Q9Y5A9|YTHDF2|len=579``.
    """
    q = (query or "").strip()
    if not q:
        return None
    fasta = catalogue_fasta_path()
    if fasta is None:
        return None
    q_up = q.upper()
    cur_hdr = ""
    chunks: list[str] = []
    try:
        with open(fasta, encoding="utf-8") as f:
            for line in f:
                if line.startswith(">"):
                    if cur_hdr and chunks:
                        parts = cur_hdr[1:].split("|")
                        keys = {p.strip().upper() for p in parts if p.strip()}
                        if q_up in keys:
                            return "".join(chunks).upper()
                    cur_hdr = line.strip()
                    chunks = []
                else:
                    chunks.append(line.strip())
            if cur_hdr and chunks:
                parts = cur_hdr[1:].split("|")
                keys = {p.strip().upper() for p in parts if p.strip()}
                if q_up in keys:
                    return "".join(chunks).upper()
    except OSError:
        return None
    return None


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
