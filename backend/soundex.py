"""Classic American Soundex phonetic encoding."""

from __future__ import annotations

import re

_CODES = {
    **{char: "1" for char in "bfpv"},
    **{char: "2" for char in "cgjkqsxz"},
    **{char: "3" for char in "dt"},
    "l": "4", "m": "5", "n": "5", "r": "6",
}


def soundex(value: str) -> str:
    letters = re.findall(r"[a-z]", value.casefold())
    if not letters:
        return ""
    first = letters[0].upper()
    previous = _CODES.get(letters[0], "")
    digits: list[str] = []
    for char in letters[1:]:
        # H and W do not break duplicate consonant groups; vowels and Y do.
        if char in "hw":
            continue
        code = _CODES.get(char, "")
        if code and code != previous:
            digits.append(code)
        previous = code
    return (first + "".join(digits) + "000")[:4]
