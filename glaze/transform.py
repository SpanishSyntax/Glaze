"""Filename transformation, word tokenization, accent stripping, and case conversion."""

from __future__ import annotations

import re
import unicodedata

CASE_OPTIONS = [
    ("title_snake", "Title_Snake_Case (e.g. My_Document_File.pdf)"),
    ("snake", "snake_case (e.g. my_document_file.pdf)"),
    ("kebab", "kebab-case (e.g. my-document-file.pdf)"),
    ("pascal", "PascalCase (e.g. MyDocumentFile.pdf)"),
    ("camel", "camelCase (e.g. myDocumentFile.pdf)"),
    ("lower", "lowercase (e.g. mydocumentfile.pdf)"),
    ("upper", "UPPERCASE (e.g. MYDOCUMENTFILE.pdf)"),
    ("upper_snake", "UPPER_SNAKE_CASE (e.g. MY_DOCUMENT_FILE.pdf)"),
]


def normalize_words(name: str) -> list[str]:
    """Splits camelCase, PascalCase, snake_case, kebab-case, dots, and spaced strings

    into a clean list of words.
    """
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    s = re.sub(r"[_.\-—–/]+", " ", s)
    s = re.sub(r"[,;:\\()\[\]{}'\"`~!@#$%^&*+=|<>?]+", " ", s)
    return [w for w in s.strip().split() if w]


def strip_accents(text: str) -> str:
    """Decomposes Unicode characters to remove diacritics (e.g., 'Café' -> 'Cafe')."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def transform_words(words: list[str], case_mode: str) -> str:
    """Transforms a list of words into the requested case mode."""
    if not words:
        return ""

    if case_mode == "title_snake":
        return "_".join(w.capitalize() for w in words)
    elif case_mode == "snake":
        return "_".join(w.lower() for w in words)
    elif case_mode == "upper_snake":
        return "_".join(w.upper() for w in words)
    elif case_mode == "kebab":
        return "-".join(w.lower() for w in words)
    elif case_mode == "pascal":
        return "".join(w.capitalize() for w in words)
    elif case_mode == "camel":
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])
    elif case_mode == "lower":
        return "".join(w.lower() for w in words)
    elif case_mode == "upper":
        return "".join(w.upper() for w in words)
    return "_".join(words)


def sanitize_filename(
    stem: str,
    ext: str,
    case_mode: str,
    safe_ascii: bool,
    lower_ext: bool,
) -> str:
    """Applies case transformation and sanitization rules to a filename."""
    if safe_ascii:
        stem = strip_accents(stem)

    words = normalize_words(stem)
    if not words:
        return ""

    new_base = transform_words(words, case_mode)

    if safe_ascii:
        new_base = re.sub(r"[^a-zA-Z0-9_\-]", "", new_base)

    # Collapse repeated delimiters and trim edge delimiters
    new_base = re.sub(r"_+", "_", new_base)
    new_base = re.sub(r"-+", "-", new_base)
    new_base = new_base.strip("_-")

    if not new_base:
        return ""

    if ext:
        final_ext = ext.lower() if lower_ext else ext
        return f"{new_base}.{final_ext}"
    return new_base
