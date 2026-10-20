"""Rename plan modeling, directory scanning, collision resolution, and execution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from glaze.history import save_undo_log
from glaze.transform import sanitize_filename
from glaze.ui import ui


@dataclass
class RenamePlan:
    """Represents a planned atomic rename operation."""

    original: Path
    new_path: Path
    relative_old: str
    relative_new: str
    is_dir: bool


def scan_directory(
    root: Path,
    extension: str,
    case_mode: str,
    safe_ascii: bool,
    lower_ext: bool,
    recursive: bool,
    include_dirs: bool,
    include_hidden: bool = False,
) -> list[RenamePlan]:
    """Scans directory and builds a conflict-checked list of planned renames."""
    plans: list[RenamePlan] = []
    clean_ext = extension.lstrip(".") if extension and extension != "*" else None

    if recursive:
        entries: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            if not include_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            dp = Path(dirpath)
            for fn in filenames:
                if fn == ".git" or fn.startswith(".git"):
                    continue
                if not include_hidden and fn.startswith("."):
                    continue
                entries.append(dp / fn)
            if include_dirs:
                for dn in dirnames:
                    entries.append(dp / dn)
        entries.sort(key=lambda p: len(p.parts), reverse=True)
    else:
        entries = sorted(list(root.iterdir()))

    for p in entries:
        if p.name == ".git" or ".git" in p.parts:
            continue

        if not include_hidden and p.name.startswith("."):
            continue

        is_directory = p.is_dir()

        if is_directory and not include_dirs:
            continue

        name = p.name

        if is_directory:
            stem = name
            ext = ""
        else:
            if "." in name and not name.startswith("."):
                stem, ext = name.rsplit(".", 1)
            else:
                stem, ext = name, ""

            if clean_ext and ext.lower() != clean_ext.lower():
                continue

        new_filename = sanitize_filename(
            stem=stem,
            ext=ext,
            case_mode=case_mode,
            safe_ascii=safe_ascii,
            lower_ext=lower_ext,
        )

        if not new_filename or new_filename == name:
            continue

        target_path = p.parent / new_filename
        rel_old = str(p.relative_to(root)) if p != root else str(p)
        rel_new = (
            str(target_path.relative_to(root))
            if target_path != root
            else str(target_path)
        )

        plans.append(
            RenamePlan(
                original=p,
                new_path=target_path,
                relative_old=rel_old,
                relative_new=rel_new,
                is_dir=is_directory,
            )
        )

    return plans


def resolve_conflicts(
    plans: list[RenamePlan],
    on_conflict: str,
    target_dir: Path,
) -> tuple[list[RenamePlan], list[RenamePlan]]:
    """Evaluates collisions and resolves them per conflict strategy ('abort', 'skip', 'suffix').

    Returns (executable_plans, collisions).
    """
    executable_plans: list[RenamePlan] = []
    collisions: list[RenamePlan] = []
    seen_destinations: set[Path] = set()

    for p in plans:
        is_collision = (
            p.new_path.exists() and p.new_path != p.original
        ) or (p.new_path in seen_destinations)

        if is_collision:
            if on_conflict == "abort":
                raise FileExistsError(
                    f"Conflict detected: target '{p.relative_new}' already exists for '{p.relative_old}'."
                )
            elif on_conflict == "suffix":
                if p.is_dir:
                    base_stem, ext = p.new_path.name, ""
                else:
                    if "." in p.new_path.name and not p.new_path.name.startswith("."):
                        base_stem, ext = p.new_path.name.rsplit(".", 1)
                    else:
                        base_stem, ext = p.new_path.name, ""
                counter = 1
                resolved_path = None
                while True:
                    suffixed_name = (
                        f"{base_stem}_{counter}.{ext}"
                        if ext
                        else f"{base_stem}_{counter}"
                    )
                    candidate_path = p.original.parent / suffixed_name
                    if (
                        not candidate_path.exists()
                        and candidate_path not in seen_destinations
                    ):
                        resolved_path = candidate_path
                        break
                    counter += 1

                p.new_path = resolved_path
                p.relative_new = (
                    str(resolved_path.relative_to(target_dir))
                    if resolved_path != target_dir
                    else str(resolved_path)
                )
                executable_plans.append(p)
                seen_destinations.add(p.new_path)
            else:  # skip
                collisions.append(p)
        else:
            executable_plans.append(p)
            seen_destinations.add(p.new_path)

    return executable_plans, collisions


def execute_renames(plans: list[RenamePlan]) -> list[tuple[str, str]]:
    """Performs the actual file / directory renames on disk, recording history."""
    executed_ops: list[tuple[str, str]] = []
    with ui.spinner(f"Renaming {len(plans)} items...") as sp:
        for p in plans:
            try:
                p.new_path.parent.mkdir(parents=True, exist_ok=True)
                p.original.rename(p.new_path)
                executed_ops.append((str(p.original), str(p.new_path)))
            except OSError as e:
                ui.error(f"Failed to rename '{p.relative_old}': {e}")
        sp.stop()

    if executed_ops:
        save_undo_log(executed_ops)
        ui.success(
            f"Successfully renamed {len(executed_ops)} item(s). Run 'glaze undo' to revert if needed."
        )
    return executed_ops
