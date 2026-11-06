"""Small edit-distance spell corrector over the indexed vocabulary."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from .text_normalizer import normalize_token


def levenshtein_distance(left: str, right: str, limit: int | None = None) -> int:
    if len(left) < len(right):
        left, right = right, left
    if len(left) - len(right) > (limit if limit is not None else len(left)):
        return (limit or 0) + 1
    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        row_min = i
        for j, char_right in enumerate(right, start=1):
            cost = 0 if char_left == char_right else 1
            value = min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost)
            current.append(value)
            row_min = min(row_min, value)
        if limit is not None and row_min > limit:
            return limit + 1
        previous = current
    return previous[-1]


class SpellCorrector:
    def __init__(self) -> None:
        self.frequency: Counter[str] = Counter()
        self.vocabulary: set[str] = set()

    def build(self, term_frequencies: dict[str, Counter[str]] | dict[str, dict[str, int]]) -> None:
        self.frequency.clear()
        for terms in term_frequencies.values():
            self.frequency.update(terms)
        self.vocabulary = set(self.frequency)

    def suggest(self, token: str, max_distance: int = 2, limit: int = 3) -> list[str]:
        normalized = normalize_token(token)
        if not normalized or normalized in self.vocabulary or len(normalized) < 3:
            return []
        # Short words are especially prone to false suggestions; use a tighter
        # edit-distance threshold for them.
        effective_limit = min(max_distance, 1) if len(normalized) <= 5 else max_distance
        candidates: list[tuple[int, int, str]] = []
        for word in self.vocabulary:
            if abs(len(word) - len(normalized)) > effective_limit:
                continue
            distance = levenshtein_distance(normalized, word, effective_limit)
            if distance <= effective_limit:
                candidates.append((distance, -self.frequency[word], word))
        candidates.sort()
        return [word for _, _, word in candidates[:limit]]
