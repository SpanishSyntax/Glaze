"""Tests for Glaze directory scanning, collision resolution, and rename execution."""

from pathlib import Path
import pytest
from glaze.engine import scan_directory, resolve_conflicts, execute_renames


def test_scan_directory(tmp_path: Path):
    (tmp_path / "My Document 1.txt").write_text("a", encoding="utf-8")
    (tmp_path / "another-file.TXT").write_text("b", encoding="utf-8")
    (tmp_path / ".hidden.txt").write_text("c", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "Nested File.txt").write_text("d", encoding="utf-8")

    plans = scan_directory(
        root=tmp_path,
        extension="txt",
        case_mode="snake",
        safe_ascii=True,
        lower_ext=True,
        recursive=False,
        include_dirs=False,
        include_hidden=False,
    )
    names = [p.original.name for p in plans]
    assert "My Document 1.txt" in names
    assert ".hidden.txt" not in names


def test_resolve_conflicts_suffix(tmp_path: Path):
    (tmp_path / "target_name.txt").write_text("existing", encoding="utf-8")
    (tmp_path / "Target Name.txt").write_text("to rename", encoding="utf-8")

    plans = scan_directory(
        root=tmp_path,
        extension="txt",
        case_mode="snake",
        safe_ascii=True,
        lower_ext=True,
        recursive=False,
        include_dirs=False,
    )
    executable, collisions = resolve_conflicts(plans, on_conflict="suffix", target_dir=tmp_path)
    assert len(executable) == 1
    assert executable[0].new_path.name == "target_name_1.txt"


def test_resolve_conflicts_abort(tmp_path: Path):
    (tmp_path / "target_name.txt").write_text("existing", encoding="utf-8")
    (tmp_path / "Target Name.txt").write_text("to rename", encoding="utf-8")

    plans = scan_directory(
        root=tmp_path,
        extension="txt",
        case_mode="snake",
        safe_ascii=True,
        lower_ext=True,
        recursive=False,
        include_dirs=False,
    )
    with pytest.raises(FileExistsError):
        resolve_conflicts(plans, on_conflict="abort", target_dir=tmp_path)


def test_execute_renames(tmp_path: Path):
    f = tmp_path / "Hello World.md"
    f.write_text("content", encoding="utf-8")
    plans = scan_directory(
        root=tmp_path,
        extension="md",
        case_mode="kebab",
        safe_ascii=True,
        lower_ext=True,
        recursive=False,
        include_dirs=False,
    )
    ops = execute_renames(plans)
    assert len(ops) == 1
    assert (tmp_path / "hello-world.md").exists()
    assert not f.exists()
