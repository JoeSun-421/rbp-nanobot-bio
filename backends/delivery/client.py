# -*- coding: utf-8 -*-
"""
=============================================================================
DeliveryToolClient — 唯一允许调用 rhobind_agent_delivery 的入口
=============================================================================

行动指南：delivery/agent/AGENT_BUILD_SPEC.md

§1 调用约定（必须遵守）
  - 每个工具两种等价入口：
      (A) CLI:  python <script> --json '<payload-json>'   → stdout 打印 JSON
      (B) 进程内:  from <module> import run; run(payload_dict) → dict
  - 标识符：{alias, uniprot}；队列 cohort: K562 | HepG2
  - 共享类型：RbpHit / Prediction（原样透传 delivery 返回值，不改写 schema）
  - 能力发现：读 delivery 的 tools/registry.json（network / gpu / status）

§2 路径：一律通过环境变量（由 env.apply_delivery_env / setup.sh 设置）
  AGENT_DB, RBP_REGISTRY, EMB_BANK, FOLDSEEK_DB, SEQ_DB, PEAKS_DB,
  AFDB_DIR, TRANSFER_DIR, USALIGN, RHOBIND_RELEASE, AF3_DIR, AF3_PARAMS, ...

§3  conda 环境（重工具必须进对的 env）
  protein_embed → foldseek / esm_*
  rna           → mmseqs (protein_seq_similarity, rna_blastn)
  rhobind       → rhobind_predict (predict_api.py)
  af3           → structure_predict_af3
  任意 python   → resolve / integrate / domain / function / rna_preprocess ...

本模块做的事（真调用，不是 mock）：
  1) 把工具名映射到 delivery 包内真实 .py 文件路径
  2) 纯 Python 工具：importlib 加载该文件 → 调用官方 run(payload)
  3) 重工具：subprocess 执行
        conda run -n <env> python <script> --json '<payload>'
     若 conda env 不存在，则退回当前解释器（会真实失败并返回 error，不假装成功）

禁止：
  - 在 agent 内重写 ESM / RhoBind / foldseek 算法
  - 修改 delivery 源码
  - 返回伪造的科学分数（没有模型就返回 ok=false + error）
=============================================================================
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from .env import apply_delivery_env, delivery_root, resolve_delivery_paths

# ---------------------------------------------------------------------------
# SPEC §3：这些工具可在任意带 numpy 的 Python 里 import run()，无需特殊 conda
# （与 AGENT_BUILD_SPEC 表格 “any python3 (+numpy)” 一致）
# ---------------------------------------------------------------------------
PURE_PYTHON_TOOLS = {
    "resolve_rbp",
    "structure_fetch",
    "pymol_util",
    "go_pfam_lookup",
    "function_category",
    "uniprot_annotation",
    "pdb_metadata",
    "literature_retrieval",
    "domain_architecture",
    "rna_preprocess",
    "similarity_weighted_vote",
    "transfer_prior_lookup",
    "confidence_abstain",
    "donor_quality_prior",
    "colabfold_msa",  # 仅 urllib，无 AF3
}

# SPEC §3：重工具 → conda 环境名
DEFAULT_CONDA_ENV: dict[str, str] = {
    "struct_similarity_foldseek": "protein_embed",
    "struct_align_usalign": "protein_embed",
    "structure_consensus": "protein_embed",
    "esm_embed": "protein_embed",
    "esm_similarity": "protein_embed",
    "protein_seq_similarity": "rna",
    "rna_blastn": "rna",
    "structure_predict_af3": "af3",
    "rhobind_predict": "rhobind",
}

# registry 工具名 → 相对 DELIVERY_ROOT 的真实脚本路径
# （与 delivery 目录布局一致；rhobind_predict 在 backbone/ 而非 tools/）
SCRIPT_MAP: dict[str, str] = {
    "resolve_rbp": "agent/tools/utility/resolve_rbp.py",
    "structure_fetch": "agent/tools/structure/structure_fetch.py",
    "structure_predict_af3": "agent/tools/structure/structure_predict_af3.py",
    "colabfold_msa": "agent/tools/structure/colabfold_msa.py",
    "structure_consensus": "agent/tools/structure/structure_consensus.py",
    "struct_similarity_foldseek": "agent/tools/structure/struct_similarity_foldseek.py",
    "struct_align_usalign": "agent/tools/structure/struct_align_usalign.py",
    "pymol_util": "agent/tools/structure/pymol_util.py",
    "protein_seq_similarity": "agent/tools/sequence/protein_seq_similarity.py",
    "esm_embed": "agent/tools/sequence/esm_embed.py",
    "esm_similarity": "agent/tools/sequence/esm_similarity.py",
    "domain_architecture": "agent/tools/sequence/domain_architecture.py",
    "rna_blastn": "agent/tools/sequence/rna_blastn.py",
    "uniprot_annotation": "agent/tools/function/uniprot_annotation.py",
    "pdb_metadata": "agent/tools/function/pdb_metadata.py",
    "literature_retrieval": "agent/tools/function/literature_retrieval.py",
    "go_pfam_lookup": "agent/tools/function/go_pfam_lookup.py",
    "function_category": "agent/tools/function/function_category.py",
    "rhobind_predict": "agent/backbone/predict_api.py",
    "rna_preprocess": "agent/tools/backbone/rna_preprocess.py",
    "similarity_weighted_vote": "agent/tools/integrate/similarity_weighted_vote.py",
    "transfer_prior_lookup": "agent/tools/integrate/transfer_prior_lookup.py",
    "confidence_abstain": "agent/tools/integrate/confidence_abstain.py",
    "donor_quality_prior": "agent/tools/integrate/donor_quality_prior.py",
}


def load_delivery_registry() -> dict[str, Any]:
    """读取 delivery 的 tools/registry.json（权威工具清单）。"""
    apply_delivery_env()
    p = resolve_delivery_paths()["registry_json"]
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def tools_meta_by_name() -> dict[str, dict[str, Any]]:
    reg = load_delivery_registry()
    return {t["name"]: t for t in reg.get("tools", []) if "name" in t}


class DeliveryToolClient:
    """
    按工具名调用 delivery 真实脚本。

    示例（与 BUILD_SPEC §1 进程内入口等价）::

        apply_delivery_env()  # 或 source agent/setup.sh
        cli = DeliveryToolClient(device="cpu")
        out = cli.call("resolve_rbp", {"query": "PTBP1"})
        # out 即 delivery resolve_rbp.run() 的返回 dict

    失败时不向调用方 raise（便于 agent 继续跑），返回::

        {"ok": False, "tool": name, "error": "...", "_latency_ms": ...}
    """

    def __init__(
        self,
        *,
        offline: bool = False,
        prefer_import: bool = True,
        device: str = "cpu",
        use_conda: bool = True,
        conda_envs: Optional[dict[str, str]] = None,
    ):
        # 每次构造都确保 AGENT_DB / RHOBIND_RELEASE 等已指向 delivery 包
        apply_delivery_env()
        self.root = delivery_root()
        self.offline = offline
        self.prefer_import = prefer_import
        self.device = device
        self.use_conda = use_conda
        self.conda_envs = {**DEFAULT_CONDA_ENV, **(conda_envs or {})}
        self.meta = tools_meta_by_name()

    def script_path(self, name: str) -> Path:
        """registry 工具名 → 磁盘上的绝对路径（必须存在，否则 FileNotFoundError）。"""
        rel = SCRIPT_MAP.get(name)
        if not rel:
            raise KeyError(
                f"No SCRIPT_MAP entry for tool {name!r}. "
                f"Add mapping or check tools/registry.json name."
            )
        p = (self.root / rel).resolve()
        if not p.is_file():
            raise FileNotFoundError(
                f"Delivery script missing for {name!r}: {p} "
                f"(DELIVERY_ROOT={self.root})"
            )
        return p

    def call(self, name: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        调用名为 ``name`` 的 delivery 工具。

        决策树
        ------
        1. offline=True 且 registry 中 network=true → 跳过（不伪造结果）
        2. gpu 工具且 payload 无 device → 填入 self.device
        3. pure-python 且 prefer_import → _call_import（真·run()）
        4. 否则 → _call_subprocess（真·CLI --json）
        """
        payload = dict(payload or {})
        t0 = time.perf_counter()
        meta = self.meta.get(name, {})

        # SPEC：headless/offline 跳过需要外网的工具
        if self.offline and meta.get("network"):
            return {
                "ok": False,
                "skipped": True,
                "tool": name,
                "error": f"offline=true; tool {name!r} requires network (registry flag)",
                "_latency_ms": 0.0,
                "_invocation": "skipped_offline",
            }

        if meta.get("gpu") and "device" not in payload:
            payload["device"] = self.device

        try:
            if self.prefer_import and name in PURE_PYTHON_TOOLS:
                out = self._call_import(name, payload)
                invocation = "import_run"
            else:
                out = self._call_subprocess(name, payload)
                invocation = "subprocess_json"

            if not isinstance(out, dict):
                out = {"value": out}
            # 不覆盖 delivery 自己的 ok 字段语义；仅在缺失时补 True
            out.setdefault("ok", True)
            out["_tool"] = name
            out["_script"] = str(self.script_path(name))
            out["_invocation"] = invocation
            out["_latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
            return out

        except Exception as e:  # noqa: BLE001 — agent 需要信封而非崩溃
            return {
                "ok": False,
                "tool": name,
                "error": f"{type(e).__name__}: {e}",
                "_script": SCRIPT_MAP.get(name),
                "_invocation": "failed",
                "_latency_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            }

    # ------------------------------------------------------------------
    # (B) 进程内：import 交付包里的 run(payload)  — BUILD_SPEC §1
    # ------------------------------------------------------------------
    def _call_import(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        等价于::

            # delivery 侧
            sys.path.insert(0, "agent/tools")
            sys.path.insert(0, "agent/tools/<category>")
            # 然后加载 <name>.py 并调用 run(payload)

        许多 delivery 工具会 ``from _common import ...``，因此必须把
        ``agent/tools`` 放进 sys.path。
        """
        script = self.script_path(name)
        tools_root = self.root / "agent" / "tools"
        for p in (str(tools_root), str(script.parent)):
            if p not in sys.path:
                sys.path.insert(0, p)

        # 用文件路径加载，避免与 agent 本地同名模块冲突
        mod_name = f"delivery_tool_{name}"
        spec = importlib.util.spec_from_file_location(mod_name, script)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {script}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

        if not hasattr(mod, "run") or not callable(mod.run):
            raise AttributeError(
                f"{script} has no callable run(payload) — not a delivery tool"
            )
        # ★ 真调用 delivery 代码
        return mod.run(payload)

    # ------------------------------------------------------------------
    # (A) CLI：python script --json '...'  — BUILD_SPEC §1
    # ------------------------------------------------------------------
    def _call_subprocess(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        等价于 shell::

            source agent/setup.sh
            conda run -n protein_embed python agent/tools/sequence/esm_similarity.py \\
                --json '{"sequence":"...","encoder":"esmc","device":"cuda"}'

        子进程继承 apply_delivery_env() 写好的环境变量，保证 _common.py
        读到正确的 AGENT_DB / EMB_BANK 等。
        """
        script = self.script_path(name)
        apply_delivery_env()
        env = os.environ.copy()

        conda_env = self.conda_envs.get(name) if self.use_conda else None
        json_arg = json.dumps(payload, ensure_ascii=False)

        if conda_env and self._conda_env_exists(conda_env):
            # Linux 生产路径：进对的科学环境
            cmd = [
                "conda",
                "run",
                "-n",
                conda_env,
                "--no-capture-output",
                "python",
                str(script),
                "--json",
                json_arg,
            ]
        else:
            # 无 conda 时仍真实执行；缺依赖则 rc!=0，由上层记入 errors
            # （绝不编造 AUPRC / binding prob）
            cmd = [sys.executable, str(script), "--json", json_arg]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(payload.get("timeout_s") or 3600),
            env=env,
            cwd=str(self.root),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"delivery tool {name!r} failed rc={proc.returncode}\n"
                f"cmd={' '.join(cmd[:6])}...\n"
                f"stderr={proc.stderr[-4000:]}\n"
                f"stdout={proc.stdout[-1500:]}"
            )
        return self._parse_json_stdout(proc.stdout)

    @staticmethod
    def _conda_env_exists(name: str) -> bool:
        try:
            r = subprocess.run(
                ["conda", "env", "list"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode != 0:
                return False
            for line in r.stdout.splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split()
                if parts and parts[0] == name:
                    return True
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _parse_json_stdout(text: str) -> dict[str, Any]:
        """解析工具 stdout 中的 JSON（允许前面有少量日志行）。"""
        text = (text or "").strip()
        if not text:
            raise ValueError("empty tool stdout")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.rfind("{")
            if start < 0:
                raise ValueError(f"no JSON object in stdout: {text[:500]!r}")
            return json.loads(text[start:])
