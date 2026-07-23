# -*- coding: utf-8 -*-
"""Write disk budget snapshot for ops (cannot expand AutoDL volume from code)."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.paths import REPORTS, ensure_artifact_dirs


def write_disk_budget(path: Path | None = None) -> Path:
    ensure_artifact_dirs()
    out = path or (REPORTS / "disk_budget.json")
    target = Path(os.environ.get("BIO_DATA_DISK", "/root/autodl-tmp"))
    usage = shutil.disk_usage(str(target) if target.exists() else "/")
    total_g = usage.total / (1024**3)
    free_g = usage.free / (1024**3)
    used_pct = 100.0 * (1.0 - usage.free / usage.total) if usage.total else 0.0
    recommend_expand = free_g < 20.0 or total_g < 80.0
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "path": str(target),
        "total_gib": round(total_g, 2),
        "free_gib": round(free_g, 2),
        "used_pct": round(used_pct, 1),
        "recommend_expand_to_gib": 100 if recommend_expand else None,
        "note": (
            "AutoDL data-disk resize is a console action; code cannot expand volume. "
            "See disk_expand_guide.md"
        ),
        "guide": str(REPORTS / "disk_expand_guide.md"),
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
