"""Dependency-free TF-IDF cosine similarity used for ticket search and duplicate detection."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence

_STOP = frozenset(
    [
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has", "have", "i",
        "if", "in", "into", "is", "it", "its", "of", "on", "or", "so", "that", "the", "their",
        "then", "there", "this", "to", "was", "were", "when", "where", "which", "while", "with",
        "after", "before", "users", "user", "does", "not", "no", "get", "gets", "got"
    ]
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in re.findall(r"[a-z0-9]+(?:[._][a-z0-9]+)*", text.lower()):
        if raw in _STOP or len(raw) < 2:
            continue
        token = raw[:-1] if raw.endswith("s") and len(raw) > 4 and not raw.endswith("ss") else raw
        tokens.append(token)
    return tokens


def _vector(tokens: Iterable[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    vec = {t: (1 + math.log(c)) * idf.get(t, 0.0) for t, c in counts.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def rank(query: str, documents: Sequence[tuple[int, str]]) -> list[tuple[int, float, list[str]]]:
    """Rank ``(doc_id, text)`` pairs against ``query``.

    Returns ``(doc_id, cosine_score, shared_terms)`` sorted by score descending.
    """
    doc_tokens = {doc_id: tokenize(text) for doc_id, text in documents}
    n_docs = max(len(doc_tokens), 1)
    df = Counter(t for tokens in doc_tokens.values() for t in set(tokens))
    idf = {t: math.log((1 + n_docs) / (1 + d)) + 1.0 for t, d in df.items()}
    q_tokens = tokenize(query)
    q_vec = _vector(q_tokens, idf | {t: idf.get(t, math.log(1 + n_docs) + 1.0)
                                     for t in q_tokens})
    results = []
    for doc_id, tokens in doc_tokens.items():
        d_vec = _vector(tokens, idf)
        shared = sorted(set(q_vec) & set(d_vec), key=lambda t: -q_vec[t] * d_vec[t])
        score = sum(q_vec[t] * d_vec[t] for t in shared)
        if score > 0:
            results.append((doc_id, round(score, 4), shared[:8]))
    results.sort(key=lambda item: -item[1])
    return results
