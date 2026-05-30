from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_FILLER = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "that",
    "this",
    "with",
}


def compress_heuristic(text: str, drop_filler: bool = True) -> str:
    """Model-free context compression: collapse whitespace, drop filler words.

    Conservative and lossless-ish for fact lines. Use LLMLingua-2 (opt-in) when
    higher compression ratios are needed; never compress system prompts.
    """
    collapsed = _WS.sub(" ", text).strip()
    if not drop_filler:
        return collapsed
    kept = [w for w in collapsed.split(" ") if w.lower() not in _FILLER]
    return " ".join(kept)
