"""
Shared topic identity matching for cross-source deduplication.

All enrichment services use these utilities so threshold tuning
happens in one place.
"""

STOP_WORDS = {
    "a", "an", "the", "in", "of", "vs", "and", "for", "to", "at",
    "by", "on", "is", "are", "was", "were", "be", "been", "has",
    "have", "had", "it", "its", "with", "as", "from", "that", "this",
    "or", "but", "not", "so", "he", "she", "they", "we", "you", "i",
    "his", "her", "their", "our", "new", "what", "how", "why", "when",
    "over", "after", "before", "about", "up", "out", "into", "will",
}


def _words(title: str) -> set:
    return set(title.lower().split()) - STOP_WORDS


def overlap_score(a: str, b: str) -> float:
    """
    Symmetric word-overlap score between two titles (0.0–1.0).
    Uses the max of both directional overlaps so short titles can
    still match long ones (e.g. 'NBA Finals' matches 'NBA Finals Game 1').
    """
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    intersection = len(wa & wb)
    return max(intersection / len(wa), intersection / len(wb))


def is_match(a: str, b: str, threshold: float = 0.45) -> bool:
    return overlap_score(a, b) >= threshold


def find_match(title: str, candidates, threshold: float = 0.45):
    """
    Return the best-matching Trend from `candidates` (any iterable with a
    `.title` attribute), or None if nothing clears `threshold`.
    """
    best, best_score = None, 0.0
    for c in candidates:
        score = overlap_score(title, c.title)
        if score >= threshold and score > best_score:
            best, best_score = c, score
    return best
