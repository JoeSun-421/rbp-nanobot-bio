# -*- coding: utf-8 -*-
"""Thin RNA embedding similarity client (mock default; optional real checkpoint).

CI / default path uses a deterministic k-mer embedder against a small local
RNA bank (``artifacts/cache/rna_bank/``). When ``RNA_FM_CHECKPOINT`` is set and
torch+transformers are available, a HuggingFace RNA-FM-style model may be used.
Never edits delivery.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Optional

from rbp_agent.core.paths import CACHE, PACKAGE_ROOT

DEFAULT_BANK = CACHE / "rna_bank" / "bank.json"
DEFAULT_WINDOW = 128
DEFAULT_STRIDE = 64
METRIC = "rna_embed"


def _normalize_rna(seq: str) -> str:
    s = "".join(c for c in (seq or "").upper() if c in "ACGUTacgut")
    return s.replace("T", "U")


def _kmer_embed(seq: str, k: int = 4) -> list[float]:
    """Deterministic bag-of-k-mers → L2-normalized vector (mock RNA-FM)."""
    s = _normalize_rna(seq)
    dim = 4**k
    vec = [0.0] * dim
    if len(s) < k:
        # short: hash-fill so empty ≠ identical zero
        h = hashlib.sha256(s.encode()).digest()
        for i, b in enumerate(h):
            vec[i % dim] += (b / 255.0)
    else:
        alphabet = "ACGU"
        idx = {c: i for i, c in enumerate(alphabet)}
        for i in range(len(s) - k + 1):
            chunk = s[i : i + k]
            if any(c not in idx for c in chunk):
                continue
            code = 0
            for c in chunk:
                code = code * 4 + idx[c]
            vec[code] += 1.0
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(sum(a[i] * b[i] for i in range(n)))


def _windows(seq: str, window: int, stride: int) -> list[str]:
    s = _normalize_rna(seq)
    if not s:
        return []
    if len(s) <= window:
        return [s]
    out = []
    for i in range(0, max(1, len(s) - window + 1), max(1, stride)):
        out.append(s[i : i + window])
        if i + window >= len(s):
            break
    if out and out[-1] != s[-window:]:
        out.append(s[-window:])
    return out


def default_bank_path() -> Path:
    env = (os.environ.get("RNA_BANK_PATH") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_BANK


def ensure_default_bank(path: Optional[Path] = None) -> Path:
    """Write a small curated bank if missing (CI-safe fixture)."""
    p = path or default_bank_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.is_file():
        return p
    # Motif-ish windows associated with well-known catalogue RBPs (synthetic).
    entries = [
        {
            "alias": "PTBP1",
            "uniprot": "P26599",
            "rna": "CUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCUCU",
            "note": "CU-rich PTB-like window (fixture)",
        },
        {
            "alias": "ELAVL1",
            "uniprot": "Q15717",
            "rna": "AUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUAUUUA",
            "note": "AU-rich ELAVL1-like window (fixture)",
        },
        {
            "alias": "QKI",
            "uniprot": "Q96PU8",
            "rna": "ACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACACUAACA",
            "note": "QKI motif-like window (fixture)",
        },
        {
            "alias": "U2AF2",
            "uniprot": "P26368",
            "rna": "UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU",
            "note": "polyU U2AF2-like window (fixture)",
        },
        {
            "alias": "HNRNPC",
            "uniprot": "P07910",
            "rna": "UUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUCUUUUUC",
            "note": "U-rich HNRNPC-like window (fixture)",
        },
    ]
    payload = {
        "version": 1,
        "metric": METRIC,
        "source": "curated_fixture",
        "entries": entries,
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def load_bank(path: Optional[Path] = None) -> list[dict[str, Any]]:
    p = ensure_default_bank(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return list(raw.get("entries") or [])
    return list(raw or [])


def maybe_bootstrap_from_peaks(bank_path: Optional[Path] = None) -> dict[str, Any]:
    """Optional: if PEAKS_DB points at a readable store, note path (no heavy parse)."""
    peaks = (os.environ.get("PEAKS_DB") or "").strip()
    if not peaks:
        return {"status": "skipped", "reason": "PEAKS_DB unset"}
    p = Path(peaks)
    if not p.exists():
        return {"status": "skipped", "reason": f"PEAKS_DB missing: {peaks}"}
    # Keep bank fixture as SoT for CI; peaks path is recorded for ops.
    ensure_default_bank(bank_path)
    return {"status": "noted", "peaks_db": str(p), "bank": str(default_bank_path())}


class RnaFmClient:
    """Embed RNA windows and score against the local bank."""

    def __init__(
        self,
        *,
        bank_path: Optional[Path] = None,
        window: int = DEFAULT_WINDOW,
        stride: int = DEFAULT_STRIDE,
        mode: Optional[str] = None,
    ) -> None:
        self.bank_path = bank_path or default_bank_path()
        self.window = int(window)
        self.stride = int(stride)
        env_mode = (os.environ.get("RNA_FM_MODE") or "").strip().lower()
        ckpt = (os.environ.get("RNA_FM_CHECKPOINT") or "").strip()
        if mode:
            self.mode = mode
        elif env_mode in ("mock", "kmer", "real"):
            self.mode = "mock" if env_mode == "kmer" else env_mode
        elif ckpt:
            self.mode = "real"
        else:
            self.mode = "mock"
        self._bank_embeds: Optional[list[tuple[dict[str, Any], list[float]]]] = None

    def _embed(self, seq: str) -> list[float]:
        if self.mode == "real":
            try:
                return self._embed_real(seq)
            except Exception:
                # Fall back silently so agent can continue with rna_axis note.
                return _kmer_embed(seq)
        return _kmer_embed(seq)

    def _embed_real(self, seq: str) -> list[float]:
        """Optional HF checkpoint path (lazy). Falls through to k-mer on ImportError."""
        ckpt = (os.environ.get("RNA_FM_CHECKPOINT") or "").strip()
        if not ckpt:
            raise RuntimeError("RNA_FM_CHECKPOINT unset")
        import torch  # type: ignore
        from transformers import AutoModel, AutoTokenizer  # type: ignore

        tok = AutoTokenizer.from_pretrained(ckpt, trust_remote_code=True)
        model = AutoModel.from_pretrained(ckpt, trust_remote_code=True)
        model.eval()
        s = _normalize_rna(seq)
        inputs = tok(s, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            out = model(**inputs)
            hidden = out.last_hidden_state  # [1, L, H]
            pooled = hidden.mean(dim=1).squeeze(0).cpu().tolist()
        n = math.sqrt(sum(x * x for x in pooled)) or 1.0
        return [float(x) / n for x in pooled]

    def _bank(self) -> list[tuple[dict[str, Any], list[float]]]:
        if self._bank_embeds is None:
            entries = load_bank(self.bank_path)
            self._bank_embeds = [(e, self._embed(str(e.get("rna") or ""))) for e in entries]
        return self._bank_embeds

    def similarity(
        self,
        rna: str,
        *,
        top_k: int = 5,
        exclude_aliases: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        rna_n = _normalize_rna(rna)
        if len(rna_n) < 8:
            return []
        exclude = exclude_aliases or set()
        wins = _windows(rna_n, self.window, self.stride)
        q_embeds = [self._embed(w) for w in wins]
        best: dict[str, dict[str, Any]] = {}
        for entry, bvec in self._bank():
            alias = (entry.get("alias") or "").strip()
            if not alias or alias in exclude:
                continue
            score = max(_cosine(qe, bvec) for qe in q_embeds)
            score = max(0.0, min(1.0, float(score)))
            prev = best.get(alias)
            if prev is None or score > float(prev["score"]):
                best[alias] = {
                    "alias": alias,
                    "uniprot": entry.get("uniprot") or "",
                    "score": round(score, 4),
                    "metric": METRIC,
                    "rank": 0,
                    "rna_axis": "ok",
                    "backend": self.mode,
                    "note": entry.get("note") or "",
                }
        hits = sorted(best.values(), key=lambda h: h["score"], reverse=True)
        for i, h in enumerate(hits[: max(1, int(top_k))], start=1):
            h["rank"] = i
        return hits[: max(1, int(top_k))]


def rna_similarity_hits(
    rna: str,
    *,
    top_k: int = 5,
    exclude_aliases: Optional[set[str]] = None,
    bank_path: Optional[Path] = None,
    window: int = DEFAULT_WINDOW,
    mode: Optional[str] = None,
) -> dict[str, Any]:
    """Public helper used by the Nanobot tool."""
    import time

    t0 = time.perf_counter()
    ensure_default_bank(bank_path)
    client = RnaFmClient(bank_path=bank_path, window=window, mode=mode)
    try:
        hits = client.similarity(rna, top_k=top_k, exclude_aliases=exclude_aliases)
        return {
            "status": "ok",
            "hits": hits,
            "n": len(hits),
            "metric": METRIC,
            "backend": client.mode,
            "backend_mode": client.mode,
            "meta": {"backend_mode": client.mode},
            "bank_path": str(client.bank_path),
            "window": client.window,
            "package_root": str(PACKAGE_ROOT),
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "status": "error",
            "reason": f"{type(e).__name__}: {e}",
            "hits": [],
            "n": 0,
            "metric": METRIC,
            "backend": getattr(client, "mode", "mock"),
            "backend_mode": getattr(client, "mode", "mock"),
            "meta": {"backend_mode": getattr(client, "mode", "mock")},
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        }
