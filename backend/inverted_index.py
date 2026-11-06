"""In-memory inverted and positional indexes."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Iterable

from .document_loader import Document
from .text_normalizer import STOP_WORDS, case_fold, stem
from .tokenizer import tokenize
from .wildcard_processor import KGramIndex
from .soundex import soundex


class InvertedIndex:
    def __init__(self, kgram_size: int = 3) -> None:
        # Retrieval postings exclude stop words; positional postings retain them
        # so phrases such as "state of the art" remain exact.
        self.postings: dict[str, dict[str, list[int]]] = defaultdict(dict)
        self.positional_postings: dict[str, dict[str, list[int]]] = defaultdict(dict)
        self.term_frequencies: dict[str, Counter[str]] = {}
        self.documents: dict[str, Document] = {}
        self.doc_lengths: dict[str, int] = {}
        self.vocabulary: set[str] = set()
        self.all_vocabulary: set[str] = set()
        self.kgram_index = KGramIndex(kgram_size)
        self.soundex_index: dict[str, set[str]] = defaultdict(set)
        self.total_tokens = 0

    def build(self, documents: Iterable[Document]) -> None:
        self.postings = defaultdict(dict)
        self.positional_postings = defaultdict(dict)
        self.term_frequencies = {}
        self.documents = {}
        self.doc_lengths = {}
        self.vocabulary = set()
        self.all_vocabulary = set()
        self.soundex_index = defaultdict(set)
        self.total_tokens = 0

        for document in documents:
            self.documents[document.doc_id] = document
            frequencies: Counter[str] = Counter()
            searchable_length = 0
            tokens = tokenize(document.text)
            self.total_tokens += len(tokens)

            for token in tokens:
                folded = case_fold(token.text)
                normalized = stem(folded)
                self.positional_postings[normalized].setdefault(document.doc_id, []).append(token.position)
                self.all_vocabulary.add(normalized)
                if folded in STOP_WORDS:
                    continue
                self.postings[normalized].setdefault(document.doc_id, []).append(token.position)
                frequencies[normalized] += 1
                searchable_length += 1

            self.term_frequencies[document.doc_id] = frequencies
            self.doc_lengths[document.doc_id] = searchable_length

        self.vocabulary = set(self.postings)
        self.kgram_index.build(self.all_vocabulary)
        for term in self.all_vocabulary:
            code = soundex(term)
            if code:
                self.soundex_index[code].add(term)

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def unique_term_count(self) -> int:
        return len(self.vocabulary)

    @property
    def source_file_count(self) -> int:
        return len({document.source for document in self.documents.values()})

    def docs_for_term(self, term: str) -> set[str]:
        return set(self.postings.get(term, {}))

    def docs_for_terms(self, terms: Iterable[str]) -> set[str]:
        result: set[str] = set()
        for term in terms:
            result.update(self.docs_for_term(term))
        return result

    def phrase_docs(self, terms: list[str]) -> set[str]:
        if not terms:
            return set()
        first_postings = self.positional_postings.get(terms[0], {})
        candidates = set(first_postings)
        for term in terms[1:]:
            candidates.intersection_update(self.positional_postings.get(term, {}))
            if not candidates:
                return set()

        matches: set[str] = set()
        for doc_id in candidates:
            positions = [set(self.positional_postings[term][doc_id]) for term in terms]
            for start in positions[0]:
                if all((start + offset) in positions[offset] for offset in range(1, len(terms))):
                    matches.add(doc_id)
                    break
        return matches

    def phonetic_terms(self, term: str) -> set[str]:
        code = soundex(term)
        return set(self.soundex_index.get(code, set())) if code else set()

    def stats(self) -> dict[str, int | str]:
        return {
            "document_count": self.document_count,
            "unique_terms": self.unique_term_count,
            "total_tokens": self.total_tokens,
            "source_files": self.source_file_count,
        }
