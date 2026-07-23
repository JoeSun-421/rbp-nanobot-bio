# -*- coding: utf-8 -*-
"""Conda-isolated RNA-FM embedding worker (no nanobot torch import).

Invoked as::

    $RNA_FM_PYTHON -m app.backends.rna_fm.worker_embed --json '{"checkpoint":"...","seqs":["ACGU"]}'

Requires ``multimolecule`` + torch in the science env (typically ``rhobind``).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any


def _normalize_rna(seq: str) -> str:
    s = "".join(c for c in (seq or "").upper() if c in "ACGUTacgut")
    return s.replace("T", "U")


def embed_seqs(checkpoint: str, seqs: list[str], *, device: str | None = None) -> list[list[float]]:
    import torch
    import multimolecule  # noqa: F401  — registers rnafm with transformers
    from multimolecule import RnaFmModel, RnaTokenizer

    tok = RnaTokenizer.from_pretrained(checkpoint)
    model = RnaFmModel.from_pretrained(checkpoint)
    model.eval()
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)

    out_vecs: list[list[float]] = []
    for raw in seqs:
        s = _normalize_rna(raw) or "A"
        inputs = tok(s, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            hidden = model(**inputs).last_hidden_state  # [1, L, H]
            pooled = hidden.mean(dim=1).squeeze(0).detach().float().cpu().tolist()
        n = math.sqrt(sum(x * x for x in pooled)) or 1.0
        out_vecs.append([float(x) / n for x in pooled])
    return out_vecs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RNA-FM embed worker")
    ap.add_argument("--json", required=True, help="JSON payload with checkpoint + seqs")
    args = ap.parse_args(argv)
    payload = json.loads(args.json)
    ckpt = str(payload.get("checkpoint") or "").strip()
    seqs = list(payload.get("seqs") or [])
    if not ckpt:
        print(json.dumps({"status": "error", "reason": "checkpoint missing"}))
        return 2
    if not seqs:
        print(json.dumps({"status": "ok", "embeddings": [], "n": 0}))
        return 0
    try:
        vecs = embed_seqs(ckpt, [str(s) for s in seqs], device=payload.get("device"))
        print(
            json.dumps(
                {
                    "status": "ok",
                    "embeddings": vecs,
                    "n": len(vecs),
                    "dim": len(vecs[0]) if vecs else 0,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as e:  # noqa: BLE001
        print(
            json.dumps(
                {"status": "error", "reason": f"{type(e).__name__}: {e}"},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
