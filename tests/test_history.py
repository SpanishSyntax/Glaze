"""Tests for Glaze undo history and logging."""

from pathlib import Path
from glaze.history import save_undo_log, run_undo


def test_save_and_run_undo(tmp_path: Path, monkeypatch):
    undo_file = tmp_path / "undo.json"
    monkeypatch.setattr("glaze.history.UNDO_LOG_PATH", undo_file)

    orig = tmp_path / "old.txt"
    renamed = tmp_path / "new.txt"
    renamed.write_text("hello", encoding="utf-8")

    save_undo_log([(str(orig), str(renamed))])
    assert undo_file.exists()

    # Dry-run test
    res = run_undo(dry_run=True)
    assert res is True
    assert renamed.exists()

    # List only test
    res_list = run_undo(list_only=True)
    assert res_list is True

    # Real revert test
    res_real = run_undo(dry_run=False, list_only=False)
    assert res_real is True
    assert orig.exists()
    assert not renamed.exists()
