"""Tests for word normalization, case transformation, and filename sanitization."""

from glaze.transform import (
    normalize_words,
    strip_accents,
    transform_words,
    sanitize_filename,
)


def test_normalize_words():
    assert normalize_words("camelCaseString") == ["camel", "Case", "String"]
    assert normalize_words("PascalCaseString") == ["Pascal", "Case", "String"]
    assert normalize_words("snake_case_name") == ["snake", "case", "name"]
    assert normalize_words("kebab-case-name") == ["kebab", "case", "name"]
    assert normalize_words("file.with.dots") == ["file", "with", "dots"]
    assert normalize_words("spaced string with (symbols) & 123") == ["spaced", "string", "with", "symbols", "123"]
    assert normalize_words("") == []


def test_strip_accents():
    assert strip_accents("café") == "cafe"
    assert strip_accents("niño") == "nino"
    assert strip_accents("münchen") == "munchen"
    assert strip_accents("façade") == "facade"
    assert strip_accents("ascii") == "ascii"


def test_transform_words():
    words = ["my", "cool", "project"]
    assert transform_words(words, "title_snake") == "My_Cool_Project"
    assert transform_words(words, "snake") == "my_cool_project"
    assert transform_words(words, "upper_snake") == "MY_COOL_PROJECT"
    assert transform_words(words, "kebab") == "my-cool-project"
    assert transform_words(words, "pascal") == "MyCoolProject"
    assert transform_words(words, "camel") == "myCoolProject"
    assert transform_words(words, "lower") == "mycoolproject"
    assert transform_words(words, "upper") == "MYCOOLPROJECT"


def test_sanitize_filename():
    res = sanitize_filename(
        stem="  My Draft - Version 01 (Reviewed)!!  ",
        ext="PDF",
        case_mode="snake",
        safe_ascii=True,
        lower_ext=True,
    )
    assert res == "my_draft_version_01_reviewed.pdf"

    res_accent = sanitize_filename(
        stem="Rapport Élève Émilie",
        ext="txt",
        case_mode="kebab",
        safe_ascii=True,
        lower_ext=True,
    )
    assert res_accent == "rapport-eleve-emilie.txt"
