# -*- coding: utf-8 -*-
"""Stage-3 verdict JSON schema validation & normalization.

Agent MVP requires every successful run to emit a structured verdict::

    {
      "label": "Strong|Likely|Unlikely|No",
      "p_hat": float,
      "confidence": "high|medium|low" | float,
      "explanation": str,
      "supporting_rbps": [ {...}, ... ]
    }
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

LABELS = ("Strong", "Likely", "Unlikely", "No")
DEFAULT_THRESHOLDS = {"strong": 0.75, "likely": 0.50, "unlikely": 0.25}


def _runtime_thresholds() -> dict[str, float]:
    try:
        from rbp_agent.core.runtime_config import label_thresholds

        return label_thresholds()
    except Exception:
        return dict(DEFAULT_THRESHOLDS)


def label_from_p_hat(
    p_hat: Optional[float],
    thresholds: Optional[dict[str, float]] = None,
) -> str:
    thr = {**_runtime_thresholds(), **(thresholds or {})}
    if p_hat is None:
        return "No"
    p = float(p_hat)
    if p >= float(thr["strong"]):
        return "Strong"
    if p >= float(thr["likely"]):
        return "Likely"
    if p >= float(thr["unlikely"]):
        return "Unlikely"
    return "No"


_FENCE_OPEN_RE = re.compile(r"```(?:json)?\s*", re.IGNORECASE)


def _balanced_json_slice(s: str, start: int) -> Optional[str]:
    """Return s[start:end] for a balanced {...} object starting at start."""
    if start < 0 or start >= len(s) or s[start] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _parse_json_object(text: str) -> Optional[dict[str, Any]]:
    """Best-effort parse of a JSON object from LLM text (fences / prose)."""
    if not text or not str(text).strip():
        return None
    s = str(text).strip()
    # Decode common double-encoding: literal \\n / \\" left in the string
    if "\\n" in s or '\\"' in s:
        try:
            s2 = codecs_decode_escapes(s)
            if s2 != s:
                s = s2.strip()
        except Exception:
            pass
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # ```json ... ```
    m = _FENCE_OPEN_RE.search(s)
    if m:
        brace = s.find("{", m.end())
        slice_ = _balanced_json_slice(s, brace) if brace >= 0 else None
        if slice_:
            try:
                obj = json.loads(slice_)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
    brace = s.find("{")
    slice_ = _balanced_json_slice(s, brace) if brace >= 0 else None
    if slice_:
        try:
            obj = json.loads(slice_)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def codecs_decode_escapes(s: str) -> str:
    """Turn literal ``\\n`` / ``\\\"`` remnants into real characters when safe."""
    if s.count("\\n") < 2 and '\\"' not in s:
        return s
    try:
        return bytes(s, "utf-8").decode("unicode_escape")
    except Exception:
        return s


def _looks_like_embedded_verdict(text: str) -> bool:
    if not isinstance(text, str):
        return False
    t = text.strip()
    if "```" in t:
        return True
    if '"label"' in t and "{" in t and "}" in t:
        return True
    return t.startswith("{") and "label" in t


def _plain_explanation(text: Any) -> str:
    """Force explanation to plain sentences — never nested JSON / fences."""
    if text is None:
        return ""
    if not isinstance(text, str):
        return str(text).strip()
    s = text.strip()
    # Repeatedly peel embedded verdict JSON
    for _ in range(4):
        if not _looks_like_embedded_verdict(s):
            break
        inner = _parse_json_object(s)
        if inner and isinstance(inner.get("explanation"), str):
            s = inner["explanation"].strip()
            continue
        # Strip fence markers even if parse failed
        s = re.sub(r"```(?:json)?", "", s, flags=re.IGNORECASE).replace("```", "").strip()
        break
    # Drop any leftover raw JSON object lines
    if s.startswith("{") and '"label"' in s:
        inner = _parse_json_object(s)
        if inner and isinstance(inner.get("explanation"), str):
            s = inner["explanation"].strip()
    return s


def _unwrap_nested_verdict(raw: dict[str, Any]) -> dict[str, Any]:
    """If LLM stuffed a full verdict JSON into explanation, prefer the inner one."""
    cur = dict(raw)
    for _ in range(4):
        expl = cur.get("explanation")
        if not _looks_like_embedded_verdict(expl if isinstance(expl, str) else ""):
            break
        inner = _parse_json_object(str(expl))
        if not inner or "label" not in inner:
            break
        merged = dict(inner)
        for k in ("mode", "caveats", "near_match", "abstain", "function_reasoning"):
            if k in cur and k not in merged:
                merged[k] = cur[k]
        # Prefer non-empty supporting_rbps from either layer
        outer_sup = cur.get("supporting_rbps") or []
        inner_sup = merged.get("supporting_rbps") or []
        if not inner_sup and outer_sup:
            merged["supporting_rbps"] = outer_sup
        cur = merged
    return cur


def normalize_verdict(
    raw: Any,
    *,
    thresholds: Optional[dict[str, float]] = None,
    default_mode: str = "unknown",
) -> dict[str, Any]:
    """Coerce pipeline/LLM output into the structured verdict object."""
    if raw is None:
        raw = {}
    if isinstance(raw, str):
        parsed = _parse_json_object(raw)
        raw = parsed if parsed is not None else {"explanation": raw, "raw_content": raw}

    if not isinstance(raw, dict):
        raw = {"raw": raw}

    # Nested under "verdict" (pipeline full result)
    if "verdict" in raw and isinstance(raw["verdict"], dict):
        inner = dict(raw["verdict"])
        # Keep useful outer fields for supporting_rbps fallback
        if "evidence_table" in raw and "supporting_rbps" not in inner:
            inner["_evidence_table"] = raw["evidence_table"]
        if raw.get("integration", {}).get("score") is not None and inner.get("p_hat") is None:
            inner["p_hat"] = raw["integration"]["score"]
        if raw.get("mode") and "mode" not in inner:
            inner["mode"] = raw["mode"]
        raw = inner

    # Unwrap double-wrapped ```json / nested verdict inside explanation
    raw = _unwrap_nested_verdict(raw)

    p_hat = raw.get("p_hat")
    if p_hat is None:
        p_hat = raw.get("score")
    if p_hat is not None:
        try:
            p_hat = float(p_hat)
        except (TypeError, ValueError):
            p_hat = None

    label = raw.get("label")
    if label not in LABELS:
        label = label_from_p_hat(p_hat, thresholds)

    # Numeric p_hat only from predictors. Missing predictor → null + hedged label.
    if p_hat is None and label in ("Strong", "Likely", "Unlikely"):
        label = "No"
        conf_forced_low = True
    else:
        conf_forced_low = False

    conf = raw.get("confidence")
    # Evidence flags from agent / integrate (scores remain tool-sourced)
    evidence_flags = raw.get("evidence_flags") or raw.get("flags") or {}
    if isinstance(evidence_flags, list):
        evidence_flags = {str(x): True for x in evidence_flags}
    prior_missing = bool(
        raw.get("prior_missing")
        or evidence_flags.get("prior_missing")
        or evidence_flags.get("loo_prior_missing")
    )
    structure_unavailable = bool(
        raw.get("structure_unavailable")
        or evidence_flags.get("structure_unavailable")
        or evidence_flags.get("structure_axis_unavailable")
    )
    force_low_evidence = prior_missing or structure_unavailable or bool(
        evidence_flags.get("sequence_only")
    )

    # Stage-3 evidence checklist (≥2 failures → confidence=low); Proposal faithfulness.
    checklist_n = raw.get("checklist_failures")
    if checklist_n is None:
        checklist_n = evidence_flags.get("checklist_failures")
    try:
        checklist_n_i = int(checklist_n) if checklist_n is not None else None
    except (TypeError, ValueError):
        checklist_n_i = None
    if checklist_n_i is None:
        # Count well-known failure flags when agent did not supply an explicit count.
        flag_fails = 0
        for key in (
            "structure_unavailable",
            "structure_axis_unavailable",
            "prior_missing",
            "loo_prior_missing",
            "domain_empty",
            "kingdom_mismatch",
            "rna_axis_unavailable",
            "sequence_only",
        ):
            if evidence_flags.get(key) or raw.get(key):
                flag_fails += 1
        if structure_unavailable:
            flag_fails = max(flag_fails, 1 if not evidence_flags else flag_fails)
        checklist_n_i = flag_fails
    if checklist_n_i >= 2:
        force_low_evidence = True

    if conf_forced_low or force_low_evidence:
        conf = "low"
    elif conf is None:
        conf = "low" if p_hat is None else ("high" if p_hat >= 0.75 or p_hat <= 0.25 else "medium")
    if isinstance(conf, (int, float)):
        c = float(conf)
        conf = "high" if c >= 0.75 else ("medium" if c >= 0.45 else "low")
    elif isinstance(conf, str):
        token = conf.strip().lower().split()[0] if conf.strip() else "low"
        token = token.strip(".,;:()")
        if force_low_evidence:
            conf = "low"
        elif token in ("high", "hi"):
            conf = "high"
        elif token in ("medium", "med", "moderate", "mid"):
            conf = "medium"
        elif token in ("low", "weak"):
            conf = "low"
        else:
            conf = "low" if p_hat is None else "medium"

    supporting = raw.get("supporting_rbps") or raw.get("supporting_RBPs") or []
    if not supporting and isinstance(raw.get("_evidence_table"), list):
        supporting = []
        for row in raw["_evidence_table"][:5]:
            supporting.append(
                {
                    "rbp_id": row.get("uniprot") or row.get("alias"),
                    "alias": row.get("alias"),
                    "prob": row.get("prob"),
                    "similarity_score": row.get("fused_similarity"),
                }
            )
    # LLM sometimes returns ["PTBP1", ...] — coerce to objects
    if isinstance(supporting, list):
        norm_sup = []
        for item in supporting:
            if isinstance(item, str):
                norm_sup.append({"rbp_id": item, "alias": item})
            elif isinstance(item, dict):
                norm_sup.append(item)
        supporting = norm_sup

    explanation = _plain_explanation(raw.get("explanation") or raw.get("summary") or "")
    if not explanation:
        explanation = (
            f"Verdict {label} with p_hat={p_hat}. "
            f"Mode={raw.get('mode') or default_mode}. "
            "Ground explanations in tool outputs when available."
        )
    # Absolute guard: never ship fences / nested JSON in explanation
    explanation = _plain_explanation(explanation)
    if "```" in explanation or (explanation.lstrip().startswith("{") and '"label"' in explanation):
        # Last resort: keep only the first prose sentence-like chunk
        explanation = re.split(r"```|\{", explanation, maxsplit=1)[0].strip() or (
            f"Own-head/transfer path finished with label={label}, p_hat={p_hat}."
        )

    out = {
        "label": label,
        "p_hat": p_hat,
        "confidence": conf,
        "explanation": explanation,
        "supporting_rbps": supporting if isinstance(supporting, list) else [],
    }
    # optional extras (not required by schema)
    for k in (
        "mode",
        "caveats",
        "near_match",
        "abstain",
        "function_reasoning",
        "prior_missing",
        "structure_unavailable",
        "evidence_flags",
    ):
        if raw.get(k) is not None:
            out[k] = raw[k]
    if force_low_evidence and "prior_missing" not in out and prior_missing:
        out["prior_missing"] = True
    if force_low_evidence and "structure_unavailable" not in out and structure_unavailable:
        out["structure_unavailable"] = True
    return out


def validate_verdict(v: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (ok, errors). MVP requires all five fields present and typed."""
    errors: list[str] = []
    if not isinstance(v, dict):
        return False, ["verdict is not a dict"]
    if v.get("label") not in LABELS:
        errors.append(f"label must be one of {LABELS}, got {v.get('label')!r}")
    ph = v.get("p_hat")
    if ph is not None:
        try:
            float(ph)
        except (TypeError, ValueError):
            errors.append("p_hat must be float or null")
    else:
        # allow null p_hat only if label is No (tools failed)
        if v.get("label") != "No":
            errors.append("p_hat is null but label is not No")
    if not v.get("explanation") or not str(v.get("explanation")).strip():
        errors.append("explanation missing")
    if "supporting_rbps" not in v:
        errors.append("supporting_rbps missing")
    elif not isinstance(v["supporting_rbps"], list):
        errors.append("supporting_rbps must be a list")
    if "confidence" not in v:
        errors.append("confidence missing")
    return (len(errors) == 0), errors


def extract_verdict_from_content(content: str) -> dict[str, Any]:
    """Parse LLM prose or pure JSON into a normalized verdict."""
    return normalize_verdict(content)


def is_near_match_score(score: Any, threshold: float = 0.95) -> bool:
    """Handle identity in [0,1] or percent [0,100]."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return False
    if s > 1.0 + 1e-9:
        return s >= threshold * 100.0
    return s >= threshold
