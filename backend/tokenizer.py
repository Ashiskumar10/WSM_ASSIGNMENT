"""Tokenization helpers for the miniature text search engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

# Keep apostrophes inside words (don't's -> don't); offsets let the UI highlight
# the original text without losing punctuation or whitespace.
TOKEN_PATTERN = re.compile(r"[\w]+(?:['’][\w]+)?", flags=re.UNICODE)


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    position: int


def tokenize(text: str) -> list[Token]:
    """Return tokens with character offsets and zero-based token positions."""
    return [
        Token(match.group(0), match.start(), match.end(), position)
        for position, match in enumerate(TOKEN_PATTERN.finditer(text))
    ]


def words(text: str) -> list[str]:
    """Return only token text, preserving the original spelling."""
    return [token.text for token in tokenize(text)]


def iter_tokens(text: str) -> Iterator[Token]:
    yield from tokenize(text)
