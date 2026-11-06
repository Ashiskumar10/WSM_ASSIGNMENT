"""Case folding, stop-word removal and a lightweight English stemmer."""

from __future__ import annotations

import re

STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "could", "did", "do", "does", "doing",
    "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your",
    "yours", "yourself", "yourselves"
})

_VOWELS = "aeiou"


def case_fold(token: str) -> str:
    return token.casefold().replace("’", "'")


def is_stop_word(token: str) -> bool:
    return case_fold(token) in STOP_WORDS


def stem(token: str) -> str:
    """A dependency-free, Porter-inspired stemmer for English demonstration corpora.

    It intentionally favors predictable behavior and compactness over the full
    Porter algorithm. It handles common plural, participle and derivational endings.
    """
    word = case_fold(token)
    if len(word) <= 3 or not word.isalpha():
        return word

    # Plurals and common inflections.
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("sses"):
        word = word[:-2]
    elif word.endswith(("ches", "shes", "xes", "zes")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]

    # -ing / -ed: remove only when a vowel remains in the stem.
    for suffix in ("ingly", "edly", "ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            base = word[:-len(suffix)]
            if any(char in _VOWELS for char in base):
                word = base
                if word.endswith(("at", "bl", "iz")):
                    word += "e"
                elif len(word) > 3 and word[-1] == word[-2] and word[-1] not in "lsz":
                    word = word[:-1]
                elif len(word) > 2 and word[-1] not in _VOWELS and word[-2] in _VOWELS:
                    word += "e"
                break

    # Common derivational endings. Apply the longest relevant suffix first.
    replacements = (
        ("ational", "ate"), ("tional", "tion"), ("fulness", "ful"),
        ("ousness", "ous"), ("iveness", "ive"), ("ization", "ize"),
        ("isation", "ize"), ("ability", "able"), ("ibility", "ible"),
        ("ness", ""), ("less", ""),
        ("ingly", ""), ("edly", ""), ("ation", "ate"), ("ator", "ate"),
        ("izer", "ize"), ("iser", "ize"), ("ously", "ous"), ("fully", "ful"),
        ("ative", ""), ("icate", "ic"), ("iciti", "ic"), ("ical", "ic"),
        ("alize", "al"), ("ative", ""), ("ance", ""), ("ence", ""),
        ("able", ""), ("ible", ""), ("ally", "al"), ("ity", ""),
        ("ous", ""), ("ive", ""), ("ize", ""), ("ise", ""),
        ("ful", ""), ("ly", ""), ("er", ""), ("est", ""), ("al", "")
    )
    for suffix, replacement in replacements:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)] + replacement
            break

    if word.endswith("y") and len(word) > 3 and word[-2] not in _VOWELS:
        word = word[:-1] + "i"
    return word


def normalize_token(token: str, *, remove_stop_words: bool = True) -> str | None:
    folded = case_fold(token)
    if not folded:
        return None
    if remove_stop_words and folded in STOP_WORDS:
        return None
    return stem(folded)


def normalize_text(text: str, *, remove_stop_words: bool = True) -> list[str]:
    from .tokenizer import words
    result: list[str] = []
    for token in words(text):
        normalized = normalize_token(token, remove_stop_words=remove_stop_words)
        if normalized:
            result.append(normalized)
    return result
