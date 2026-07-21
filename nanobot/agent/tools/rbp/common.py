# -*- coding: utf-8 -*-
"""
Shared helpers for RBP tools.

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
    """Locate nanobot-bio root and put it on sys.path."""
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

    def _is_bio_root(c: Path) -> bool:
        return (c / "rbp_agent" / "backends" / "delivery" / "client.py").is_file() or (
            c / "backends" / "delivery" / "client.py"
        ).is_file()

    for c in candidates:
        try:
            c = c.resolve()
        except OSError:
            continue
        if _is_bio_root(c):
            if str(c) not in sys.path:
                sys.path.append(str(c))
            os.environ.setdefault("NANOBOT_BIO_ROOT", str(c))
            return c
    raise FileNotFoundError(
        "Cannot find nanobot-bio (rbp_agent/backends/delivery). "
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
    from rbp_agent.backends.delivery.client import DeliveryToolClient
    from rbp_agent.backends.delivery.env import apply_delivery_env

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


def looks_like_accession_or_alias(text: str) -> bool:
    """True if ``text`` is a UniProt/gene token, not a protein AA string."""
    s = (text or "").strip()
    if not s or len(s) > 32 or any(ch.isspace() for ch in s):
        return False
    # UniProt accession (e.g. O43251, Q9Y5A9, P26599, A0A0B4J2F0)
    import re

    if re.fullmatch(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}", s, re.I):
        return True
    # Gene / alias tokens (RBFOX2, PTBP1) — short, no digits-only, mostly alnum
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{1,24}", s) and any(c.isalpha() for c in s):
        # Reject obvious AA peptides (high fraction of valid AA letters, length>=20 handled elsewhere)
        if len(s) <= 15:
            return True
    return False


def looks_like_rna(seq: str) -> bool:
    s = (seq or "").strip().upper().replace(" ", "")
    if len(s) < 8:
        return False
    return set(s) <= set("ACGTUN")


def looks_like_dummy_protein(seq: str) -> bool:
    """Detect invented poly-X / poly-A junk the LLM sometimes fabricates."""
    s = (seq or "").strip().upper().replace(" ", "")
    if len(s) < 20:
        return False
    from collections import Counter

    c = Counter(s)
    top_n, top_cnt = c.most_common(1)[0]
    if top_cnt / len(s) >= 0.85 and top_n in "ACDEFGHIKLMNPQRSTVWY":
        return True
    return False


def fetch_uniprot_sequence(accession: str, *, timeout: float = 25.0) -> Optional[str]:
    """Fetch AA sequence from UniProt REST FASTA (agent-side; does not edit delivery)."""
    import re
    import time
    import urllib.error
    import urllib.request

    acc = (accession or "").strip().upper()
    if not re.fullmatch(
        r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}",
        acc,
    ):
        return None
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    last_err: Optional[BaseException] = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            lines = [
                ln.strip()
                for ln in text.splitlines()
                if ln.strip() and not ln.startswith(">")
            ]
            seq = "".join(lines).upper()
            if len(seq) >= 20:
                return seq
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt == 0:
                time.sleep(0.6)
    del last_err
    return None


def resolve_protein_sequence(kwargs: dict[str, Any]) -> tuple[str, Optional[str]]:
    """Resolve AA sequence from kwargs.

    Returns ``(sequence, source)`` where source is
    ``sequence`` | ``catalogue`` | ``uniprot_rest`` | None.
    If ``sequence``/``target_sequence`` is actually an accession/alias, load FASTA
    (or UniProt REST for accessions outside the RBP catalogue).
    """
    raw = (kwargs.get("sequence") or kwargs.get("target_sequence") or "").strip()
    if raw and looks_like_accession_or_alias(raw):
        loaded = load_catalogue_sequence(raw)
        if loaded:
            return loaded, "catalogue"
        # UniProt accession outside catalogue → REST (never treat ID as AA)
        rest = fetch_uniprot_sequence(raw)
        if rest:
            return rest, "uniprot_rest"
        return "", None
    if raw and looks_like_rna(raw):
        return "", None
    if raw and looks_like_dummy_protein(raw):
        return "", None
    if raw and len(raw) >= 20:
        return raw.upper(), "sequence"

    for key in ("alias", "uniprot", "query", "rbp_id", "name"):
        q = kwargs.get(key)
        if not q:
            continue
        q = str(q).strip()
        loaded = load_catalogue_sequence(q)
        if loaded:
            return loaded, "catalogue"
        rest = fetch_uniprot_sequence(q)
        if rest:
            return rest, "uniprot_rest"
    return (raw.upper() if raw and len(raw) >= 20 else ""), None


def not_in_catalogue_hint(*ids: str) -> str:
    """Short reason when tools fail because the protein is outside RhoBind K."""
    shown = "/".join(x for x in ids if x) or "this protein"
    return (
        f"{shown} is not in the RhoBind RBP catalogue (~238). "
        "seq/struct catalogue tools need a real AA `sequence` (auto-fetched from "
        "UniProt when you pass a valid accession), or abstain with p_hat=null / "
        "confidence=low. Do not invent sequences or loop AF3."
    )


def catalogue_pdb_path(*, uniprot: str = "", alias: str = "") -> Optional[Path]:
    """Resolve AFDB PDB under ``AFDB_DIR`` (``ALIAS_UNIPROT.pdb``)."""
    afdb = os.environ.get("AFDB_DIR")
    if not afdb:
        return None
    root = Path(afdb)
    if not root.is_dir():
        return None
    u = (uniprot or "").strip()
    a = (alias or "").strip()
    cands: list[Path] = []
    if a and u:
        cands.append(root / f"{a}_{u}.pdb")
    if u:
        cands.extend(root.glob(f"*_{u}.pdb"))
        cands.append(root / f"{u}.pdb")
    if a:
        cands.extend(root.glob(f"{a}_*.pdb"))
    for p in cands:
        if p.is_file():
            return p
    return None


def _structure_cache_dir() -> Path:
    try:
        root = ensure_nanobot_bio_on_path()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from rbp_agent.core.paths import STRUCTURE_CACHE, ensure_artifact_dirs

        ensure_artifact_dirs()
        return STRUCTURE_CACHE
    except Exception:
        fallback = Path(os.environ.get("NANOBOT_BIO_ROOT", ".")) / "artifacts" / "cache" / "structure"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def structure_cache_get(key: str, *, ttl_s: float = 7 * 24 * 3600) -> Optional[dict[str, Any]]:
    """Return cached structure-tool payload if fresh (success or failure)."""
    import hashlib

    safe = hashlib.sha256(key.encode("utf-8")).hexdigest()[:40]
    path = _structure_cache_dir() / f"{safe}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = float(data.get("ts") or 0)
        if time.time() - ts > float(ttl_s):
            return None
        return data.get("payload")
    except Exception:
        return None


def structure_cache_put(key: str, payload: dict[str, Any]) -> None:
    """Disk-cache AF3/structure results (including failures) to avoid 200s+ repeats."""
    import hashlib

    safe = hashlib.sha256(key.encode("utf-8")).hexdigest()[:40]
    path = _structure_cache_dir() / f"{safe}.json"
    try:
        path.write_text(
            json.dumps({"ts": time.time(), "key": key, "payload": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


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
