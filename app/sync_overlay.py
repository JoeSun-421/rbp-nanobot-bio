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


def _rel_link_target(src: Path, dst_file: Path) -> str:
    """Return a *relative* symlink target for ``src`` from the dir of ``dst_file``.

    Relative (not absolute) so the committed symlink is portable across hosts
    (an absolute ``/root/...`` path is unreadable on CI runners and breaks
    ``os.stat`` with PermissionError). Computed from ``dst_file``'s *lexical*
    parent dir (not the resolved target) so it works before the link exists."""
    import posixpath

    return posixpath.relpath(src.resolve(), start=dst_file.parent.resolve())


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
    # NANOBOT_SRC is the *destination* runtime tree (editable checkout). On some
    # upstream layouts the package lives in a subdir (no __init__.py at repo
    # root), so this check is non-fatal: we warn and skip the NANOBOT_SRC-side
    # copy, but still mirror into the *imported* nanobot (site-packages / editable
    # target) via _mirror_tools_to_imported — that is what pytest/CLI actually
    # import.
    nanobot_src_ok = (nanobot_src / "__init__.py").is_file() or (
        nanobot_src / "nanobot.py"
    ).is_file()
    if not nanobot_src_ok:
        print(
            "WARN: NANOBOT_SRC does not look like nanobot runtime root:",
            nanobot_src,
            "(skipping NANOBOT_SRC-side copy; will still mirror into imported nanobot)",
            file=sys.stderr,
        )

    dst_rbp = nanobot_src / "agent" / "tools" / "rbp"
    if nanobot_src_ok:
        dst_rbp.parent.mkdir(parents=True, exist_ok=True)
    dest_skill_dir = workspace / "skills" / "rbp-agent"
    dest_skill = dest_skill_dir / "SKILL.md"
    runtime_skill = nanobot_src / "skills" / "rbp-agent" / "SKILL.md"
    src_skill_dir = src_skill.parent

    def _link_or_copy_skill(dst_file: Path) -> str:
        """Prefer a *relative* symlink to the SoT skill; fall back to copy2.

        Relative (not absolute) so the symlink is portable across machines /
        CI runners (an absolute path like ``/root/...`` is unreadable on other
        hosts and breaks ``os.stat`` with PermissionError)."""
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        if dst_file.is_symlink():
            try:
                if os.readlink(dst_file) == _rel_link_target(src_skill, dst_file):
                    return "symlink-fresh"
            except Exception:
                pass
            dst_file.unlink()
        elif dst_file.exists():
            try:
                if dst_file.resolve() == src_skill.resolve():
                    return "copy-fresh"
            except Exception:
                pass
            dst_file.unlink()
        try:
            os.symlink(_rel_link_target(src_skill, dst_file), dst_file)
            return "symlink"
        except OSError:
            shutil.copy2(src_skill, dst_file)
            return "copy"

    tools_fresh = _same_tree(src_rbp, dst_rbp)

    def _skill_ok(dst_file: Path) -> bool:
        """True iff dst_file is a symlink/file already pointing at the SoT skill.

        Robust to broken / permission-denied symlinks (e.g. an absolute
        ``/root/...`` symlink committed from another host): ``os.stat`` on such
        a target raises PermissionError, so we stat with ``follow_symlinks``
        guarded and fall back to comparing the link text."""
        try:
            if dst_file.is_symlink():
                return os.readlink(dst_file) == _rel_link_target(src_skill, dst_file)
            if dst_file.is_file():
                return dst_file.resolve() == src_skill.resolve()
        except (OSError, ValueError):
            return False
        return False

    skill_ws_ok = _skill_ok(dest_skill)
    skill_rt_ok = _skill_ok(runtime_skill)
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
                        need = os.readlink(dest_refs) != _rel_link_target(
                            src_refs, dest_refs
                        )
                    except (OSError, ValueError):
                        need = True
                if need:
                    if dest_refs.exists() or dest_refs.is_symlink():
                        if dest_refs.is_symlink() or dest_refs.is_file():
                            dest_refs.unlink()
                        else:
                            shutil.rmtree(dest_refs)
                    try:
                        os.symlink(_rel_link_target(src_refs, dest_refs), dest_refs)
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

    if not nanobot_src_ok:
        # NANOBOT_SRC unusable (e.g. upstream restructured to a subdir). For
        # pytest/CLI the only thing that matters is that the *imported* nanobot
        # (site-packages / editable target) carries the SoT rbp overlay — mirror
        # that and return. Workspace/runtime skill linking is a CLI-runtime concern
        # (best-effort, never fatal) and is skipped here to avoid permission
        # issues on read-only CI checkouts.
        _mirror_tools_to_imported(src_rbp, dst_rbp, _log)
        _log("[sync_overlay] NANOBOT_SRC-side skill/tool copy skipped (runtime root unavailable)")
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
            # Skip if already a correct relative symlink (portable across hosts).
            try:
                if dest_refs.is_symlink() and os.readlink(dest_refs) == _rel_link_target(
                    src_refs, dest_refs
                ):
                    continue
            except (OSError, ValueError):
                pass
            if dest_refs.exists() or dest_refs.is_symlink():
                if dest_refs.is_symlink() or dest_refs.is_file():
                    dest_refs.unlink()
                else:
                    shutil.rmtree(dest_refs)
            try:
                os.symlink(_rel_link_target(src_refs, dest_refs), dest_refs)
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
