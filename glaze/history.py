"""Undo log tracking and reversal engine for Glaze."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from glaze.ui import ui

UNDO_LOG_PATH = Path(
    os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
) / "glaze" / "undo.json"


def get_undo_log_path() -> Path:
    """Returns the persistent path for the undo operation log."""
    return UNDO_LOG_PATH


def save_undo_log(operations: list[tuple[str, str]]) -> None:
    """Saves executed rename pairs [(old_path, new_path), ...] to state log."""
    if not operations:
        return
    log_path = get_undo_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    records = [{"old": old, "new": new} for old, new in operations]
    log_path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def run_undo(dry_run: bool = False, list_only: bool = False) -> bool:
    """Reverses the most recent batch rename session from the persistent log."""
    log_path = get_undo_log_path()
    if not log_path.exists():
        ui.error(f"No undo log found at '{log_path}'.")
        return False

    try:
        data = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception as e:
        ui.error(f"Failed to read undo log: {e}")
        return False

    if not data:
        ui.warn("Undo log is empty.")
        return False

    if dry_run or list_only:
        lines = []
        for item in reversed(data):
            old_p = Path(item["old"])
            new_p = Path(item["new"])
            if not new_p.exists():
                tag = ui.yellow("[MISSING]")
            elif old_p.exists():
                tag = ui.red("[COLLISION]")
            else:
                tag = ui.green("[REVERSIBLE]")
            lines.append(
                f"{tag} {ui.dim(new_p.name)} {ui.cyan('→')} {ui.bold(old_p.name)}"
            )
        ui.panel(f"GLAZE UNDO LOG ({len(data)} operations)", lines)
        ui.info("Dry-run preview only. No files were modified.", symbol="💡")
        return True

    if sys.stdin.isatty():
        confirm = ui.select(
            f"Undo {len(data)} rename operation(s)?",
            [
                ("yes", f"Yes, revert {len(data)} file(s) to original names"),
                ("no", "No, keep current names"),
            ],
        )
        if confirm != "yes":
            ui.warn("Undo aborted by user.")
            return True

    reversed_ops: list[dict[str, str]] = []
    success_count = 0
    failure_count = 0

    with ui.spinner("Reversing rename operations...") as sp:
        for item in reversed(data):
            old_p = Path(item["old"])
            new_p = Path(item["new"])

            if not new_p.exists():
                ui.warn(f"Cannot revert '{new_p}': file does not exist.")
                failure_count += 1
                continue

            if old_p.exists() and old_p != new_p:
                ui.error(
                    f"Collision during revert: original name '{old_p}' already exists."
                )
                failure_count += 1
                continue

            try:
                old_p.parent.mkdir(parents=True, exist_ok=True)
                new_p.rename(old_p)
                reversed_ops.append(item)
                success_count += 1
            except OSError as e:
                ui.error(f"Failed to revert '{new_p}' -> '{old_p}': {e}")
                failure_count += 1

        sp.stop()

    if failure_count == 0:
        ui.success(f"Successfully reverted all {success_count} file(s).")
        try:
            log_path.unlink()
        except OSError:
            pass
        return True
    else:
        ui.warn(
            f"Reverted {success_count} file(s) with {failure_count} failure(s)."
        )
        remaining = [item for item in data if item not in reversed_ops]
        save_undo_log([(r["old"], r["new"]) for r in remaining])
        return False
