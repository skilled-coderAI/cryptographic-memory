from __future__ import annotations

from cryptomem.verification.faithfulness import split_sentences

_FILLER_PREFIXES = ("[mock]", "answer using", "verified facts", "question:")


def extract_facts(text: str, min_words: int = 4) -> list[str]:
    """Pull declarative, fact-like sentences from free text (model-free).

    Keeps reasonably long, non-interrogative statements and drops obvious
    instruction/boilerplate lines. This is a deliberately conservative
    heuristic: write-back stages candidates as ``pending`` for confirmation,
    so precision matters more than recall.
    """
    facts: list[str] = []
    for sentence in split_sentences(text):
        stripped = sentence.strip()
        lower = stripped.lower()
        if stripped.endswith("?"):
            continue
        if any(lower.startswith(prefix) for prefix in _FILLER_PREFIXES):
            continue
        if len(stripped.split()) < min_words:
            continue
        facts.append(stripped)
    return facts
