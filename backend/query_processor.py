"""Boolean query parser and query-term extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .tokenizer import words


class QueryParseError(ValueError):
    pass


@dataclass
class QueryPlan:
    ast: Any
    positive_terms: list[str]


_TOKEN_PATTERN = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|\(|\)|[^\s()]+')


def lex_boolean_query(query: str) -> list[str]:
    return _TOKEN_PATTERN.findall(query)


def parse_boolean_query(query: str) -> QueryPlan:
    tokens = lex_boolean_query(query)
    if not tokens:
        raise QueryParseError("Enter a query to search.")
    parser = _BooleanParser(tokens)
    ast = parser.parse_expression()
    if parser.position != len(tokens):
        raise QueryParseError(f"Unexpected token: {tokens[parser.position]}")
    positive_terms: list[str] = []
    _collect_positive_terms(ast, positive_terms)
    return QueryPlan(ast=ast, positive_terms=positive_terms)


class _BooleanParser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.position = 0

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def consume(self) -> str:
        token = self.peek()
        if token is None:
            raise QueryParseError("Unexpected end of query.")
        self.position += 1
        return token

    @staticmethod
    def _is_operator(token: str | None, operator: str) -> bool:
        return token is not None and token.upper() == operator

    def parse_expression(self) -> Any:
        return self.parse_or()

    def parse_or(self) -> Any:
        node = self.parse_and()
        while self._is_operator(self.peek(), "OR"):
            self.consume()
            node = ("OR", node, self.parse_and())
        return node

    def _starts_unary(self, token: str | None) -> bool:
        return token is not None and token != ")" and token.upper() not in {"AND", "OR"}

    def parse_and(self) -> Any:
        node = self.parse_unary()
        while True:
            if self._is_operator(self.peek(), "AND"):
                self.consume()
                node = ("AND", node, self.parse_unary())
            elif self._starts_unary(self.peek()):
                # Adjacent atoms in Boolean mode imply AND.
                node = ("AND", node, self.parse_unary())
            else:
                break
        return node

    def parse_unary(self) -> Any:
        if self._is_operator(self.peek(), "NOT"):
            self.consume()
            return ("NOT", self.parse_unary())
        token = self.consume()
        if token == "(":
            node = self.parse_or()
            if self.peek() != ")":
                raise QueryParseError("Missing closing parenthesis.")
            self.consume()
            return node
        if token == ")" or token.upper() in {"AND", "OR"}:
            raise QueryParseError(f"Unexpected operator: {token}")
        if token.startswith('"') and token.endswith('"'):
            phrase = token[1:-1].replace('\\"', '"').strip()
            phrase_words = words(phrase)
            if not phrase_words:
                raise QueryParseError("Phrase is empty.")
            return ("PHRASE", phrase)
        return ("TERM", token)


def _collect_positive_terms(node: Any, result: list[str], negated: bool = False) -> None:
    kind = node[0]
    if kind == "NOT":
        _collect_positive_terms(node[1], result, not negated)
    elif kind in {"AND", "OR"}:
        _collect_positive_terms(node[1], result, negated)
        _collect_positive_terms(node[2], result, negated)
    elif not negated and kind == "TERM":
        result.extend(words(node[1]))
    elif not negated and kind == "PHRASE":
        result.extend(words(node[1]))


def contains_boolean_syntax(query: str) -> bool:
    in_quotes = False
    outside: list[str] = []
    for char in query:
        if char == '"':
            in_quotes = not in_quotes
        elif not in_quotes:
            outside.append(char)
    plain = "".join(outside)
    return bool(re.search(r"\b(?:AND|OR|NOT)\b|[()]", plain, flags=re.IGNORECASE))
