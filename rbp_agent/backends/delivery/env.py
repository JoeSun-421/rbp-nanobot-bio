"""Resolve DELIVERY_ROOT and key paths without modifying delivery code."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def delivery_root() -> Path:
    """Package root of rhobind_agent_delivery."""
    env = os.environ.get("DELIVERY_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # Default: sibling of nanobot-bio under bio_agent/
    here = Path(__file__).resolve()
    # .../nanobot-bio/rbp_agent/backends/delivery/env.py → parents[4] = bio_agent
    candidate = here.parents[4] / "rhobind_agent_delivery"
    if candidate.is_dir():
        return candidate.resolve()
    # Legacy layout (backends at repo root)
    legacy = here.parents[3] / "rhobind_agent_delivery"
    if legacy.is_dir():
        return legacy.resolve()
    raise FileNotFoundError(
        "DELIVERY_ROOT not set and sibling rhobind_agent_delivery not found. "
        "export DELIVERY_ROOT=/path/to/rhobind_agent_delivery"
    )


def resolve_delivery_paths() -> dict[str, Path]:
    root = delivery_root()
    return {
        "delivery_root": root,
        "tools_root": root / "agent" / "tools",
        "registry_json": root / "agent" / "tools" / "registry.json",
        "predict_api": root / "agent" / "backbone" / "predict_api.py",
        "agent_db": Path(os.environ.get("AGENT_DB", root / "agent_db")),
        "rbp_registry": Path(
            os.environ.get(
                "RBP_REGISTRY",
                root / "agent_db" / "registry" / "rbp_registry.json",
            )
        ),
        "rhobind_release": Path(
            os.environ.get(
                "RHOBIND_RELEASE",
                root / "release" / "rhobind_release_v1",
            )
        ),
        "setup_sh": root / "agent" / "setup.sh",
        "examples": root / "agent" / "examples",
    }


@lru_cache(maxsize=1)
def load_rbp_registry() -> dict[str, Any]:
    paths = resolve_delivery_paths()
    reg_path = paths["rbp_registry"]
    if not reg_path.is_file():
        raise FileNotFoundError(f"RBP registry not found: {reg_path}")
    with open(reg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("rbp_registry.json must be a dict keyed by UniProt")
    return data


def _default_hf_home() -> str:
    """Prefer ``HF_HOME``; else ``$XDG_CACHE_HOME/huggingface`` / ``~/.cache/huggingface``."""
    if os.environ.get("HF_HOME"):
        return str(Path(os.environ["HF_HOME"]).expanduser())
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return str(Path(xdg).expanduser() / "huggingface")
    return str(Path.home() / ".cache" / "huggingface")


def apply_delivery_env() -> dict[str, str]:
    """Set standard delivery env vars if missing (mirrors setup.sh defaults)."""
    root = delivery_root()
    hf_home = _default_hf_home()
    # Mirrors agent/setup.sh + AGENT_BUILD_SPEC §2
    defaults = {
        "DELIVERY_ROOT": str(root),
        "AGENT_DB": str(root / "agent_db"),
        "RBP_REGISTRY": str(root / "agent_db" / "registry" / "rbp_registry.json"),
        "RHOBIND_RELEASE": str(root / "release" / "rhobind_release_v1"),
        "RBP_PROTEINS": str(root / "reference"),
        "AFDB_DIR": str(root / "reference" / "structures" / "afdb"),
        "TRANSFER_DIR": str(root / "agent_db" / "transfer"),
        "EMB_BANK": str(root / "agent_db" / "embedding_bank"),
        "FOLDSEEK_DB": str(root / "agent_db" / "foldseek_db" / "refs"),
        "SEQ_DB": str(root / "agent_db" / "seq_db" / "refs"),
        "PEAKS_DB": str(root / "agent_db" / "peaks_db" / "peaks"),
        "USALIGN": str(root / "agent_db" / "bin" / "USalign"),
        "AF3_DIR": str(root / "agent" / "third_party" / "alphafold3"),
        "AF3_PARAMS": str(root / "af3_assets" / "alphafold_param"),
        # AF3_PYTHON left to conda env after setup_envs.sh / setup_af3.sh
        # ESM / HF: AutoDL often cannot reach huggingface.co — use local cache + mirror
        "HF_HOME": hf_home,
        "HUGGINGFACE_HUB_CACHE": str(Path(hf_home) / "hub"),
        "TRANSFORMERS_CACHE": str(Path(hf_home) / "transformers"),
        "HF_ENDPOINT": "https://hf-mirror.com",
    }
    applied = {}
    for k, v in defaults.items():
        if k not in os.environ:
            os.environ[k] = v
            applied[k] = v
        else:
            applied[k] = os.environ[k]
    Path(applied["HF_HOME"]).mkdir(parents=True, exist_ok=True)
    Path(applied["HUGGINGFACE_HUB_CACHE"]).mkdir(parents=True, exist_ok=True)
    Path(applied["TRANSFORMERS_CACHE"]).mkdir(parents=True, exist_ok=True)
    return applied
