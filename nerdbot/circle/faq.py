"""Answer free-form Cultist Circle questions from the FAQ without an LLM.

Each entry is scored on two signals: hand-picked keywords that appear in the question
(longer phrases count for more) and fuzzy similarity to the entry's own question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process, utils

from .knowledge import FAQ, INCOMPATIBLE_ITEMS, SIX_HOUR_EXCLUSIONS, FaqEntry

MIN_SCORE = 35.0


@dataclass(frozen=True, slots=True)
class Answer:
    entry: FaqEntry | None
    score: float
    related: tuple[FaqEntry, ...]


def _norm(text: str) -> str:
    """Lowercase, strip punctuation and drop plural 's' so 'figurines' hits 'figurine'."""
    words = utils.default_process(text).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)


_STOPWORDS = frozenset(
    "a an the is are was be do doe does did i my me we you it its of for to in on at and or "
    "what whats why how can could will would some any this that there here with from".split()
)


def _content(text: str) -> str:
    return " ".join(w for w in text.split() if w not in _STOPWORDS)


_PREPARED = [
    (
        entry,
        _content(_norm(entry.question)),
        tuple(sorted({_norm(k) for k in entry.keywords}, key=len, reverse=True)),
    )
    for entry in FAQ
]


def _keyword_score(q: str, keywords: tuple[str, ...]) -> float:
    padded = f" {q} "
    score = 0.0
    for kw in keywords:
        if f" {kw} " in padded:
            # Multi-word phrases are much stronger evidence than a single word.
            score += 14 + 6 * (kw.count(" "))
    return min(score, 60.0)


def score_entries(question: str) -> list[tuple[FaqEntry, float]]:
    q = _norm(question)
    if not q:
        return []
    content = _content(q)
    scored = []
    for entry, entry_q, keywords in _PREPARED:
        text = fuzz.token_set_ratio(content, entry_q) * 0.5 if content else 0.0
        scored.append((entry, text + _keyword_score(q, keywords)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def ask(question: str) -> Answer:
    ranked = score_entries(question)
    if not ranked:
        return Answer(None, 0.0, tuple(e for e in FAQ[:4]))
    best, score = ranked[0]
    related = tuple(e for e, s in ranked[1:4] if s >= MIN_SCORE)
    if score < MIN_SCORE:
        return Answer(None, score, tuple(e for e, _ in ranked[:4]))
    return Answer(best, score, related)


def entry_by_id(entry_id: str) -> FaqEntry | None:
    return next((e for e in FAQ if e.id == entry_id), None)


def search_questions(text: str, limit: int = 25) -> list[FaqEntry]:
    """Autocomplete helper: FAQ entries ordered by relevance to partial input."""
    if not text.strip():
        return list(FAQ[:limit])
    return [e for e, s in score_entries(text)[:limit] if s > 15] or list(FAQ[:limit])


_SACRIFICE_RE = re.compile(
    r"^(?:can|could) (?:i|you|we) (?:sacrifice|use|put|burn|throw)\s+(?:an?\s+|the\s+|my\s+)?(.+?)"
    r"(?:\s+(?:in|into) (?:the )?(?:circle|ritual))?\s*\??$",
    re.IGNORECASE,
)
_SIX_HOUR_RE = re.compile(
    r"(?:get|receive|return|drop|come back|give).*\b6\s*h|6\s*h(?:our)?.*(?:return|give|drop|reward)",
    re.IGNORECASE,
)


def sacrifice_subject(question: str) -> str | None:
    """Pull the item out of 'can I sacrifice X?' style questions."""
    match = _SACRIFICE_RE.match(question.strip())
    return match.group(1).strip() if match else None


def incompatible_match(name: str) -> str | None:
    """Return the matching incompatible item name, if the item can't be sacrificed."""
    hit = process.extractOne(
        name, INCOMPATIBLE_ITEMS, scorer=fuzz.WRatio, processor=utils.default_process, score_cutoff=88
    )
    return hit[0] if hit else None


_SIX_HOUR_ALIASES = {
    "LEDX Skin Transilluminator": ("ledx",),
    "Far-forward GPS Signal Amplifier Unit": ("gps amplifier", "gps signal amplifier", "far forward gps", "gps unit"),
    "Advanced current converter": ("advanced current converter", "current converter", "acc"),
}


def six_hour_excluded(name: str) -> str | None:
    """Exclusion entry for an exact item name ("LedX*" on the site is a prefix match)."""
    key = utils.default_process(name)
    for excluded in SIX_HOUR_EXCLUSIONS:
        target = utils.default_process(excluded)
        if key == target or (excluded.startswith("LEDX") and key.startswith("ledx")):
            return excluded
    return None


def six_hour_mentioned(text: str) -> str | None:
    """Find an excluded item named anywhere in free text, by known aliases."""
    padded = f" {utils.default_process(text)} "
    for excluded, aliases in _SIX_HOUR_ALIASES.items():
        if any(f" {a} " in padded for a in aliases):
            return excluded
    return None


def mentions_six_hour_reward(question: str) -> bool:
    return bool(_SIX_HOUR_RE.search(question))
