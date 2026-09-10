"""Text normalization helpers for dedup + light HTML stripping."""

from __future__ import annotations

import re
import html


_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")
_SUFFIX_CO = re.compile(
    r"[,\s]+(inc|inc\.|llc|ltd|ltd\.|corp|corp\.|corporation|co|co\.)$",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^a-z0-9]+")


def strip_html(html_str: str) -> str:
    """Very light HTML → text. Enough for LLM downstream reading of a JD."""
    if not html_str:
        return ""
    # unescape entities, drop tags, collapse whitespace.
    text = html.unescape(html_str)
    text = _TAG.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def normalize_company(name: str) -> str:
    if not name:
        return ""
    n = name.strip().lower()
    n = _SUFFIX_CO.sub("", n)
    n = _NON_WORD.sub("", n)
    return n


def normalize_title(title: str) -> str:
    if not title:
        return ""
    n = title.strip().lower()
    # remove common parenthetical suffixes
    n = re.sub(r"\([^)]*\)", "", n)
    # unify level tokens
    n = re.sub(r"\b(new grad|newgrad|new graduate|entry level|entry-level|university grad|university graduate|early career|nyc?|sf|remote|hybrid)\b", "", n)
    n = _NON_WORD.sub("", n)
    return n
