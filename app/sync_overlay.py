# -*- coding: utf-8 -*-
"""Sync plugin SoT (tools + skill) into the installed nanobot runtime.

Source of truth (Proposal §6.2 overlay)::
    nanobot-bio/nanobot/skills/rbp-agent/SKILL.md
    nanobot-bio/nanobot/agent/tools/rbp/*.py

Destination (runtime, default $BIO_ROOT/nanobot or site-packages)::
    $NANOBOT_SRC/agent/tools/rbp/
    $NANOBOT_WORKSPACE/skills/rbp-agent/SKILL.md
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path


def _tree_sig(root: Path) -> str:
    """Stable signature of *.py / SKILL.md under root (path + size + mtime_ns)."""
    if not root.exists():
        return ""
    parts: list[str] = []
    if root.is_file():
        st = root.stat()
        parts.append(f"{root.name}:{st.st_size}:{st.st_mtime_ns}")
    else:
        for p in sorted(root.rglob("*")):
            if p.name in ("__pycache__", ".pytest_cache") or p.suffix == ".pyc":
                continue
            if p.is_dir():
                continue
            if p.suffix not in (".py", ".md") and p.name != "SKILL.md":
                continue
            rel = p.relative_to(root).as_posix()
            st = p.stat()
            parts.append(f"{rel}:{st.st_size}:{st.st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _same_tree(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return False
    return _tree_sig(src) == _tree_sig(dst) and _tree_sig(src) != ""


def _mirror_tools_to_imported(src_rbp: Path, dst_rbp: Path, log) -> None:
    """Best-effort: mirror the rbp overlay into the *imported* nanobot package.

    A non-editable ``pip install nanobot-ai`` leaves a frozen copy of the nanobot
    package in site-packages that shadows the runtime source (NANOBOT_SRC) at
    import time. Without this mirror, pytest and the CLI see a stale rbp overlay
    and the SoT edits never take effect. Skipped when nanobot isn't importable
    or the resolved root equals the runtime source.
    """
    try:
        import nanobot as _nb  # noqa: F401

        imported_rbp = Path(_nb.__file__).resolve().parent / "agent" / "tools" / "rbp"
        if imported_rbp.resolve() == dst_rbp.resolve() or not imported_rbp.is_dir():
            return
        if _same_tree(src_rbp, imported_rbp):
            log("[sync_overlay] tools (imported) skip-if-fresh")
            return
        if imported_rbp.exists():
            shutil.rmtree(imported_rbp)
        imported_rbp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            src_rbp,
            imported_rbp,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
        log(f"[sync_overlay] tools (imported) -> {imported_rbp}")
    except Exception as exc:  # pragma: no cover - best-effort mirror
        log(f"[sync_overlay] tools (imported) mirror skipped: {exc!r}")



def sync_overlay(*, quiet: bool = False) -> int:
    """Copy SoT tools + skill into runtime nanobot. Return process exit code."""
    from app.sot import skill_md, sot_root, tools_rbp

    bio = Path(
        os.environ.get("NANOBOT_BIO_ROOT", Path(__file__).resolve().parents[1])
    ).expanduser().resolve()
    bio_root = Path(os.environ.get("BIO_ROOT", bio.parent)).expanduser().resolve()
    sot = sot_root()
    src_rbp = tools_rbp()
    src_skill = skill_md()

    nanobot_src = Path(
        os.environ.get("NANOBOT_SRC", bio_root / "nanobot")
    ).expanduser().resolve()
    workspace = Path(
        os.environ.get("NANOBOT_WORKSPACE", bio / "workspace")
    ).expanduser().resolve()

    def _log(msg: str) -> None:
        if not quiet:
            print(msg)

    _log(f"[sync_overlay] SoT={sot}")
    _log(f"[sync_overlay] NANOBOT_SRC={nanobot_src}")
    _log(f"[sync_overlay] WORKSPACE={workspace}")

    if not src_rbp.is_dir():
        print("ERROR: missing SoT tools at", src_rbp, file=sys.stderr)
        return 1
    if not src_skill.is_file():
        print("ERROR: missing SoT skill at", src_skill, file=sys.stderr)
        return 1
    if not (nanobot_src / "__init__.py").is_file() and not (
        nanobot_src / "nanobot.py"
    ).is_file():
        print(
            "ERROR: NANOBOT_SRC does not look like nanobot runtime:",
            nanobot_src,
            file=sys.stderr,
        )
        return 1

    dst_rbp = nanobot_src / "agent" / "tools" / "rbp"
    dst_rbp.parent.mkdir(parents=True, exist_ok=True)
    dest_skill_dir = workspace / "skills" / "rbp-agent"
    dest_skill = dest_skill_dir / "SKILL.md"
    runtime_skill = nanobot_src / "skills" / "rbp-agent" / "SKILL.md"
    src_skill_dir = src_skill.parent

    def _link_or_copy_skill(dst_file: Path) -> str:
        """Prefer symlink to SoT skill; fall back to copy2."""
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        if dst_file.is_symlink() or dst_file.exists():
            try:
                if dst_file.resolve() == src_skill.resolve():
                    return "symlink-fresh"
            except Exception:
                pass
            dst_file.unlink()
        try:
            os.symlink(src_skill.resolve(), dst_file)
            return "symlink"
        except OSError:
            shutil.copy2(src_skill, dst_file)
            return "copy"

    tools_fresh = _same_tree(src_rbp, dst_rbp)
    skill_ws_ok = (
        dest_skill.is_file()
        or dest_skill.is_symlink()
    ) and (
        dest_skill.resolve() == src_skill.resolve()
        if dest_skill.exists() or dest_skill.is_symlink()
        else False
    )
    skill_rt_ok = (
        runtime_skill.is_file() or runtime_skill.is_symlink()
    ) and (
        runtime_skill.resolve() == src_skill.resolve()
        if runtime_skill.exists() or runtime_skill.is_symlink()
        else False
    )
    if tools_fresh and skill_ws_ok and skill_rt_ok:
        # Still refresh references/ when present (progressive disclosure assets)
        src_refs = src_skill_dir / "references"
        if src_refs.is_dir():
            for dest_dir in (dest_skill_dir, runtime_skill.parent):
                dest_refs = dest_dir / "references"
                need = True
                if dest_refs.is_dir() and not dest_refs.is_symlink():
                    need = not _same_tree(src_refs, dest_refs)
                elif dest_refs.is_symlink():
                    try:
                        need = dest_refs.resolve() != src_refs.resolve()
                    except Exception:
                        need = True
                if need:
                    if dest_refs.exists() or dest_refs.is_symlink():
                        if dest_refs.is_symlink() or dest_refs.is_file():
                            dest_refs.unlink()
                        else:
                            shutil.rmtree(dest_refs)
                    try:
                        os.symlink(src_refs.resolve(), dest_refs)
                    except OSError:
                        shutil.copytree(src_refs, dest_refs)
        marker = dest_skill_dir / "DO_NOT_EDIT.md"
        if not marker.is_file():
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                "# Generated by sync — do not hand-edit\n\n"
                "Edit SoT: nanobot/skills/rbp-agent/SKILL.md\n"
                "Then: python -m app.sync_overlay  or  nanobot-bio doctor\n",
                encoding="utf-8",
            )
        _log("[sync_overlay] skip-if-fresh: tools + skill already in sync")
        _mirror_tools_to_imported(src_rbp, dst_rbp, _log)
        return 0

    if not tools_fresh:
        if dst_rbp.exists():
            shutil.rmtree(dst_rbp)
        shutil.copytree(
            src_rbp,
            dst_rbp,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
        _log(f"[sync_overlay] tools -> {dst_rbp}")
        _log(
            "[sync_overlay] tools: "
            + str(sorted(p.name for p in dst_rbp.iterdir() if p.suffix == ".py"))
        )
        _mirror_tools_to_imported(src_rbp, dst_rbp, _log)
    else:
        _log("[sync_overlay] tools skip-if-fresh")
        _mirror_tools_to_imported(src_rbp, dst_rbp, _log)

    how_ws = _link_or_copy_skill(dest_skill)
    _log(f"[sync_overlay] skill ({how_ws}) -> {dest_skill}")
    # Progressive-disclosure references/ (nanobot skill layout)
    src_refs = src_skill_dir / "references"
    if src_refs.is_dir():
        for dest_dir in (dest_skill_dir, runtime_skill.parent):
            dest_refs = dest_dir / "references"
            if dest_refs.exists() or dest_refs.is_symlink():
                if dest_refs.is_symlink() or dest_refs.is_file():
                    dest_refs.unlink()
                else:
                    shutil.rmtree(dest_refs)
            try:
                os.symlink(src_refs.resolve(), dest_refs)
                _log(f"[sync_overlay] references symlink -> {dest_refs}")
            except OSError:
                shutil.copytree(src_refs, dest_refs)
                _log(f"[sync_overlay] references copy -> {dest_refs}")
    marker = dest_skill_dir / "DO_NOT_EDIT.md"
    marker.write_text(
        "# Generated by sync — do not hand-edit\n\n"
        "Edit SoT: nanobot/skills/rbp-agent/SKILL.md\n"
                "Then: python -m app.sync_overlay  or  nanobot-bio doctor\n",
        encoding="utf-8",
    )

    how_rt = _link_or_copy_skill(runtime_skill)
    _log(f"[sync_overlay] skill runtime ({how_rt}) -> {runtime_skill}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return sync_overlay()


if __name__ == "__main__":
    raise SystemExit(main())
