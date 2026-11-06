"""K-gram-based wildcard expansion."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable


class KGramIndex:
    def __init__(self, k: int = 3) -> None:
        self.k = k
        self.grams: dict[str, set[str]] = defaultdict(set)
        self.vocabulary: set[str] = set()

    def build(self, vocabulary: Iterable[str]) -> None:
        self.grams.clear()
        self.vocabulary = set(vocabulary)
        for term in self.vocabulary:
            padded = f"${term}$"
            for index in range(max(0, len(padded) - self.k + 1)):
                self.grams[padded[index:index + self.k]].add(term)

    def _literal_grams(self, pattern: str) -> set[str]:
        grams: set[str] = set()
        for segment in re.split(r"[*?]+", pattern):
            if len(segment) >= self.k:
                grams.update(segment[index:index + self.k] for index in range(len(segment) - self.k + 1))
        return grams

    def expand(self, pattern: str) -> list[str]:
        """Find wildcard matches using k-gram candidates followed by regex checks."""
        if not any(char in pattern for char in "*?"):
            return [pattern] if pattern in self.vocabulary else []
        grams = self._literal_grams(pattern)
        if grams:
            candidate_sets = [self.grams.get(gram, set()) for gram in grams]
            if any(not values for values in candidate_sets):
                return []
            candidates = set.intersection(*(set(values) for values in candidate_sets))
        else:
            candidates = set(self.vocabulary)
        regex = "^" + "".join(".*" if char == "*" else "." if char == "?" else re.escape(char) for char in pattern) + "$"
        matcher = re.compile(regex)
        return sorted(term for term in candidates if matcher.fullmatch(term))


def expand_wildcard(pattern: str, kgram_index: KGramIndex) -> list[str]:
    return kgram_index.expand(pattern)
