"""Tell an English question from a French one, from its function words alone.

The BM25 branch stems French and matches French words. On an English question it can only
match numbers and acronyms, and on the dev split its candidates then push the dense ones
down instead of adding to them. The search uses this guess to leave BM25 out of English
questions. No model is involved: the same question always gets the same answer, and the
cost is a set lookup per word.
"""

from __future__ import annotations

import re


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# Short, frequent words that belong to one language only; "a" or "en" would vote for both.
_ENGLISH = _words(
    "the of and to is are what which who when how does do can must should would under "
    "for with from this that their there be been has have an any its it"
)
_FRENCH = _words(
    "le la les des du de un une est sont que qui quoi quel quelle quels quelles quand "
    "comment doit doivent peut peuvent pour avec dans sur ce cette ses leur au aux et ou "
    "il elle ne pas"
)
_WORD = re.compile(r"[a-zàâçéèêëîïôûùüÿœ']+", re.IGNORECASE)


def is_english(text: str) -> bool:
    """True when English function words outnumber French ones; ties count as French.

    French is the language of the corpus, so a question the counter cannot place keeps
    both branches, which is the behaviour the search had before this guess existed.
    """
    words = [w.strip("'").lower() for w in _WORD.findall(text)]
    # "l'article", "qu'un": the elided form carries the French marker.
    elided = sum(1 for w in words if re.match(r"^(?:l|d|qu|j|n|s|c)'", w))
    english = sum(1 for w in words if w in _ENGLISH)
    french = sum(1 for w in words if w in _FRENCH) + elided
    return english > french
