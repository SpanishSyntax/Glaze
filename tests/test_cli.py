"""Tests for Glaze CLI parsing and options."""

from pathlib import Path
from glaze import __version__
from glaze.cli import main


def test_cli_version(capsys):
    ret = main(["--version"])
    assert ret == 0
    captured = capsys.readouterr()
    assert f"v{__version__}" in captured.out


def test_cli_help(capsys):
    ret = main(["--help"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Universal Filename Sanitizer" in captured.out


def test_cli_dry_run(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Old Name.txt").write_text("data", encoding="utf-8")
    ret = main(["--snake", "--dry-run"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "GLAZE BATCH RENAME ENGINE" in captured.out
    assert "Dry-run complete" in captured.out
    assert (tmp_path / "Old Name.txt").exists()
