"""TF-IDF cosine ranking."""

from __future__ import annotations

import math
from collections import Counter
from typing import Iterable

from .inverted_index import InvertedIndex


def inverse_document_frequency(index: InvertedIndex, term: str) -> float:
    document_frequency = len(index.postings.get(term, {}))
    return math.log((index.document_count + 1) / (document_frequency + 1)) + 1.0


def rank_documents(
    index: InvertedIndex,
    candidates: Iterable[str],
    query_terms: Iterable[str],
) -> list[tuple[str, float]]:
    """Rank candidate ids by cosine similarity of TF-IDF vectors."""
    candidate_ids = set(candidates)
    if not candidate_ids:
        return []

    query_frequency = Counter(term for term in query_terms if term in index.vocabulary)
    if not query_frequency:
        return [(doc_id, 0.0) for doc_id in candidate_ids]

    query_weights: dict[str, float] = {}
    for term, frequency in query_frequency.items():
        query_weights[term] = (1.0 + math.log(frequency)) * inverse_document_frequency(index, term)
    query_norm = math.sqrt(sum(weight * weight for weight in query_weights.values())) or 1.0

    ranked: list[tuple[str, float]] = []
    for doc_id in candidate_ids:
        frequencies = index.term_frequencies.get(doc_id, Counter())
        doc_norm_sq = 0.0
        dot_product = 0.0
        for term, frequency in frequencies.items():
            weight = (1.0 + math.log(frequency)) * inverse_document_frequency(index, term)
            doc_norm_sq += weight * weight
            if term in query_weights:
                dot_product += weight * query_weights[term]
        doc_norm = math.sqrt(doc_norm_sq) or 1.0
        score = dot_product / (doc_norm * query_norm)
        ranked.append((doc_id, score))

    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked
