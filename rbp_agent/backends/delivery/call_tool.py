"""Invoke a delivery tool script with --json (skeleton).

Real implementation will use conda run -n <env> when needed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from .env import resolve_delivery_paths


def call_delivery_script(
    script_rel: str,
    payload: dict[str, Any],
    *,
    conda_env: Optional[str] = None,
    python: Optional[str] = None,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Run: [conda run -n env] python <delivery>/<script_rel> --json '<payload>'.

    Returns parsed JSON dict from stdout, or raises RuntimeError.
    """
    root = resolve_delivery_paths()["delivery_root"]
    script = (root / script_rel).resolve()
    if not script.is_file():
        raise FileNotFoundError(f"Delivery script missing: {script}")

    py = python or sys.executable
    cmd: list[str]
    if conda_env:
        cmd = [
            "conda",
            "run",
            "-n",
            conda_env,
            "--no-capture-output",
            "python",
            str(script),
            "--json",
            json.dumps(payload),
        ]
    else:
        cmd = [py, str(script), "--json", json.dumps(payload)]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"delivery tool failed rc={proc.returncode}: {proc.stderr[-2000:]}"
        )
    text = proc.stdout.strip()
    # Tools may print pretty JSON; take last JSON object if mixed logs
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try last line
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
        raise
