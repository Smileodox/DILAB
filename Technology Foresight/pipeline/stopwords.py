"""Stop words and keyword filters for technology-foresight topic labeling."""
from __future__ import annotations

import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Academic / paper boilerplate that rarely names a technology area
EXTRA_STOP_WORDS = {
    "also", "among", "article", "based", "between", "both", "can", "could",
    "different", "each", "et", "al", "etc", "even", "experimental", "experiments",
    "fig", "figure", "findings", "first", "further", "furthermore", "given",
    "hence", "here", "however", "introduction", "journal", "large", "level",
    "levels", "main", "many", "may", "might", "moreover", "much", "must",
    "namely", "new", "novel", "number", "one", "paper", "papers", "part",
    "particular", "particularly", "per", "performance", "present", "presented",
    "previous", "previously", "problem", "problems", "propose", "proposed",
    "provide", "provided", "recent", "related", "report", "reported", "research",
    "respectively", "result", "results", "review", "section", "several", "show",
    "showed", "shown", "shows", "significant", "similar", "since", "solution",
    "solutions", "specific", "specifically", "study", "studies", "such", "table",
    "there", "therefore", "these", "they", "this", "those", "thus", "two",
    "use", "used", "using", "various", "very", "via", "well", "whether",
    "within", "without", "work", "would", "yet",
    # Ultra-common in ML abstracts but not discriminative alone
    "able", "across", "addition", "additional", "analysis", "application",
    "applications", "approach", "approaches", "area", "areas", "case", "cases",
    "compared", "comparison", "consider", "considered", "data", "dataset",
    "datasets", "demonstrate", "demonstrated", "design", "designed", "developed",
    "development", "effect", "effects", "example", "examples", "existing",
    "following", "found", "framework", "general", "given", "high", "higher",
    "important", "including", "information", "known", "like", "low", "lower",
    "made", "make", "method", "methods", "need", "needed", "note", "observed",
    "obtained", "order", "possible", "potential", "present", "process",
    "proposed", "proposes", "respect", "set", "several", "several", "shown",
    "similar", "simple", "single", "small", "state", "technique", "techniques",
    "terms", "three", "thus", "type", "types", "used", "useful", "value",
    "values", "way", "ways",
}

FORESIGHT_STOP_WORDS = frozenset(ENGLISH_STOP_WORDS) | EXTRA_STOP_WORDS

# Terms too short or non-semantic to label a cluster (even if not in sklearn list)
BLOCKED_TOKENS = frozenset(
    {
        "etc", "ie", "eg", "vs", "ref", "refs", "doi", "arxiv", "org", "com",
        "www", "http", "https", "pdf", "version", "vol", "pp", "ed", "eds",
    }
)


def is_valid_keyword(term: str) -> bool:
    """Return True if term is suitable for foresight topic labels."""
    w = term.strip().lower()
    if not w or w in FORESIGHT_STOP_WORDS or w in BLOCKED_TOKENS:
        return False
    if len(w) < 3 or w.isdigit():
        return False
    if not re.search(r"[a-z]", w):
        return False
    # Drop tokens that are mostly digits (e.g. years mistaken as terms)
    if sum(c.isdigit() for c in w) / len(w) > 0.4:
        return False
    return True


def filter_keyword_list(keywords: list[tuple[str, float]] | list[str], limit: int = 12) -> list[str]:
    """Keep ranked keywords that pass foresight filters."""
    out: list[str] = []
    for item in keywords:
        word = item[0] if isinstance(item, (list, tuple)) else str(item)
        if is_valid_keyword(word) and word.lower() not in {k.lower() for k in out}:
            out.append(word.lower() if word.islower() else word)
        if len(out) >= limit:
            break
    return out


def get_vectorizer_stop_words() -> list[str]:
    return sorted(FORESIGHT_STOP_WORDS)
