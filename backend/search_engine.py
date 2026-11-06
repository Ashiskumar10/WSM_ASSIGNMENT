"""Orchestrates indexing, Boolean/ranked retrieval, correction and snippets."""

from __future__ import annotations

import html
import re
from collections import Counter
from typing import Any

from .document_loader import Document
from .inverted_index import InvertedIndex
from .query_processor import QueryParseError, contains_boolean_syntax, parse_boolean_query
from .ranking import rank_documents
from .spell_corrector import SpellCorrector
from .text_normalizer import case_fold, normalize_token
from .tokenizer import tokenize, words


class SearchEngine:
    def __init__(self) -> None:
        self.index = InvertedIndex()
        self.spell_corrector = SpellCorrector()
        self.indexed = False

    def build(self, documents: list[Document]) -> None:
        self.index.build(documents)
        self.spell_corrector.build(self.index.term_frequencies)
        self.indexed = True

    def stats(self) -> dict[str, int | str]:
        result = self.index.stats()
        result["status"] = "ready" if self.indexed else "empty"
        return result

    def _normalize_phrase(self, phrase: str) -> list[str]:
        return [normalize_token(word, remove_stop_words=False) for word in words(phrase)]

    def _term_expansions(self, raw_term: str, phonetic: bool) -> list[str]:
        term = case_fold(raw_term)
        if any(char in term for char in "*?"):
            # Stem the literal runs without changing wildcard operators.
            pieces = re.split(r"([*?]+)", term)
            pattern = "".join(
                piece if piece and all(char in "*?" for char in piece)
                else (normalize_token(piece, remove_stop_words=False) or piece)
                for piece in pieces
            )
            return self.index.kgram_index.expand(pattern)
        normalized = normalize_token(term)
        if not normalized:
            return []
        expansions = {normalized} if normalized in self.index.all_vocabulary else set()
        if phonetic:
            expansions.update(self.index.phonetic_terms(normalized))
        return sorted(expansions)

    def _term_docs(self, raw_term: str, phonetic: bool) -> tuple[set[str], list[str]]:
        # Treat punctuation-separated subwords (for example, TF-IDF) as
        # adjacent terms in Boolean expressions too. Wildcard characters stay
        # attached to their token and are expanded through the K-gram index.
        atoms = re.findall(r"[A-Za-z0-9_]*[*?][A-Za-z0-9_*?]*|[A-Za-z0-9_]+", raw_term)
        if len(atoms) > 1:
            atom_results = [self._term_expansions(atom, phonetic) for atom in atoms]
            term_sets = [self.index.docs_for_terms(terms) for terms in atom_results]
            docs = set.intersection(*term_sets) if term_sets else set()
            return docs, [term for terms in atom_results for term in terms]
        expansions = self._term_expansions(atoms[0] if atoms else raw_term, phonetic)
        return self.index.docs_for_terms(expansions), expansions

    def _phrase_docs(self, phrase: str) -> tuple[set[str], list[str]]:
        normalized = self._normalize_phrase(phrase)
        return self.index.phrase_docs(normalized), [term for term in normalized if term]

    def _eval_boolean(self, node: Any, phonetic: bool) -> tuple[set[str], list[str]]:
        kind = node[0]
        universe = set(self.index.documents)
        if kind == "TERM":
            return self._term_docs(node[1], phonetic)
        if kind == "PHRASE":
            return self._phrase_docs(node[1])
        if kind == "NOT":
            docs, _ = self._eval_boolean(node[1], phonetic)
            return universe - docs, []
        left_docs, left_terms = self._eval_boolean(node[1], phonetic)
        right_docs, right_terms = self._eval_boolean(node[2], phonetic)
        if kind == "AND":
            return left_docs & right_docs, left_terms + right_terms
        return left_docs | right_docs, left_terms + right_terms

    def _ranked_candidates(self, query: str, phonetic: bool) -> tuple[set[str], list[str], list[str]]:
        candidate_docs: set[str] = set()
        ranking_terms: list[str] = []
        highlight_terms: list[str] = []
        # Quoted segments are exact positional phrases.
        pieces = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"|([^"\s]+)', query)
        for phrase, plain in pieces:
            if phrase:
                docs, phrase_terms = self._phrase_docs(phrase)
                candidate_docs.update(docs)
                ranking_terms.extend(term for term in phrase_terms if term in self.index.vocabulary)
                highlight_terms.extend(phrase_terms)
                continue
            if not plain or plain.upper() in {"AND", "OR", "NOT"}:
                continue
            if plain in {"(", ")"}:
                continue
            # Split punctuation such as the hyphen in TF-IDF into searchable
            # word tokens while keeping wildcard operators attached to a term.
            atoms = re.findall(r"[A-Za-z0-9_]*[*?][A-Za-z0-9_*?]*|[A-Za-z0-9_]+", plain)
            for atom in atoms:
                docs, expansions = self._term_docs(atom, phonetic)
                candidate_docs.update(docs)
                ranking_terms.extend(expansions)
                highlight_terms.extend(expansions)
        return candidate_docs, ranking_terms, highlight_terms

    def _correct_query(self, query: str) -> tuple[str, list[dict[str, str]]]:
        corrections: list[dict[str, str]] = []
        pattern = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|[A-Za-z][A-Za-z\']*')

        def replace(match: re.Match[str]) -> str:
            value = match.group(0)
            if value.startswith('"'):
                inner = value[1:-1]
                corrected_inner = self._correct_words(inner, corrections)
                return f'"{corrected_inner}"'
            if value.upper() in {"AND", "OR", "NOT"}:
                return value
            return self._correct_word(value, corrections)

        corrected = pattern.sub(replace, query)
        return corrected, corrections

    def _correct_words(self, phrase: str, corrections: list[dict[str, str]]) -> str:
        return re.sub(r"[A-Za-z][A-Za-z']*", lambda m: self._correct_word(m.group(0), corrections), phrase)

    def _correct_word(self, word: str, corrections: list[dict[str, str]]) -> str:
        if any(char in word for char in "*?"):
            return word
        normalized = normalize_token(word)
        if not normalized or normalized in self.index.all_vocabulary:
            return word
        suggestions = self.spell_corrector.suggest(word, max_distance=1, limit=1)
        if suggestions:
            replacement = suggestions[0]
            corrections.append({"original": word, "suggestion": replacement})
            return replacement
        return word

    def _snippet_html(self, text: str, highlight_terms: set[str], max_length: int = 360) -> str:
        if len(text) > max_length:
            text = text[:max_length].rsplit(" ", 1)[0] + "…"
        tokens = tokenize(text)
        pieces: list[str] = []
        cursor = 0
        for token in tokens:
            pieces.append(html.escape(text[cursor:token.start]))
            normalized = normalize_token(token.text, remove_stop_words=False)
            escaped = html.escape(token.text)
            if normalized in highlight_terms:
                pieces.append(f"<mark>{escaped}</mark>")
            else:
                pieces.append(escaped)
            cursor = token.end
        pieces.append(html.escape(text[cursor:]))
        return "".join(pieces)

    def _run_once(self, query: str, mode: str, phonetic: bool) -> tuple[list[tuple[str, float]], list[str], list[str], str]:
        effective_mode = mode
        if mode == "ranked" and contains_boolean_syntax(query):
            effective_mode = "boolean"

        if effective_mode == "boolean":
            plan = parse_boolean_query(query)
            candidates, raw_highlight_terms = self._eval_boolean(plan.ast, phonetic)
            query_terms: list[str] = []
            for raw in plan.positive_terms:
                if raw.upper() in {"AND", "OR", "NOT"}:
                    continue
                query_terms.extend(self._term_expansions(raw, phonetic))
            highlight_terms = list(raw_highlight_terms)
            for raw in plan.positive_terms:
                highlight_terms.extend(self._normalize_phrase(raw))
            ranked = rank_documents(self.index, candidates, query_terms)
        else:
            candidates, query_terms, highlight_terms = self._ranked_candidates(query, phonetic)
            ranked = rank_documents(self.index, candidates, query_terms)
        return ranked, query_terms, highlight_terms, effective_mode

    def search(
        self,
        query: str,
        mode: str = "ranked",
        phonetic: bool = False,
        spell_correct: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        if not self.indexed:
            return {"results": [], "total": 0, "message": "No corpus is indexed yet. Upload TXT files to begin.", "corrected_query": None, "suggestions": []}
        if not query or not query.strip():
            raise ValueError("Enter a search query.")
        if mode not in {"ranked", "boolean", "wildcard"}:
            mode = "ranked"

        query = query.strip()
        try:
            ranked, query_terms, highlight_terms, effective_mode = self._run_once(query, mode, phonetic)
        except QueryParseError as error:
            raise ValueError(str(error)) from error

        corrected_query: str | None = None
        suggestions: list[dict[str, str]] = []
        if spell_correct:
            corrected, suggestions = self._correct_query(query)
        else:
            corrected = query
        if spell_correct and corrected.casefold() != query.casefold():
            try:
                corrected_ranked, corrected_terms, corrected_highlights, corrected_mode = self._run_once(corrected, mode, phonetic)
                # A corrected query is used only when it produces a useful set
                # of matches and does not reduce the original result set.
                if corrected_ranked and len(corrected_ranked) >= len(ranked):
                    ranked, query_terms, highlight_terms, effective_mode = corrected_ranked, corrected_terms, corrected_highlights, corrected_mode
                    corrected_query = corrected
            except QueryParseError:
                pass

        results: list[dict[str, Any]] = []
        for rank, (doc_id, score) in enumerate(ranked[:limit], start=1):
            document = self.index.documents[doc_id]
            terms = set(highlight_terms)
            results.append({
                "rank": rank,
                "doc_id": doc_id,
                "title": document.title,
                "source": document.source,
                "paragraph_number": document.paragraph_number,
                "snippet": document.text[:360],
                "snippet_html": self._snippet_html(document.text, terms),
                "score": round(score, 6),
                "score_percent": round(score * 100, 1),
                "matched_terms": sorted(terms),
            })

        return {
            "results": results,
            "total": len(ranked),
            "mode": effective_mode,
            "phonetic": phonetic,
            "spell_correct": spell_correct,
            "corrected_query": corrected_query,
            "suggestions": suggestions,
            "message": "" if ranked else "No matching documents were found. Try a broader query or check the spelling.",
        }
