"""Reference regex guard, French and English.

It is the floor every model has to beat, and the safety net kept in production behind
the classifier: rules are cheap, deterministic and explainable to an auditor. Each rule
asks for an attack shape (a verb aimed at the assistant's own instructions), not a
scary word, so "comment ignorer un test de non-régression" stays a normal question.
"""

from __future__ import annotations

import re
import unicodedata

from guardbench.guards.base import Guard, Verdict

# Patterns run on lower-cased text with accents removed, hence "systeme" not "système".
_OVERRIDE_VERB = (
    r"(ignore[rsz]?|disregard|forget|oublie[rsz]?|override|outrepasse[rsz]?"
    r"|ne tiens? (plus )?compte d[eu]|fais abstraction d[eu])"
)
_INSTRUCTIONS = r"(instructions?|consignes?|regles|directives?|prompts?|guidelines|rules)"
_AIMED = (
    r"(previous|prior|above|earlier|preceding|initial|original|system|your|all|any"
    r"|precedentes?|anterieures?|ci-dessus|initiales?|systeme|tes|vos|toutes?)"
)

RULES: tuple[tuple[str, str], ...] = (
    (
        "instruction_override",
        rf"\b{_OVERRIDE_VERB}\b[^.\n]{{0,40}}\b{_AIMED}\b[^.\n]{{0,25}}\b{_INSTRUCTIONS}\b",
    ),
    (
        "instruction_override",
        rf"\b{_INSTRUCTIONS}\s+(precedentes?|anterieures?|ci-dessus|initiales?)\b"
        rf"[^.\n]{{0,30}}\b(sont|is|are)\s+(annulees?|obsoletes?|void|cancelled|revoked)",
    ),
    (
        # "Ignore the rules" alone is a fair compliance question; aiming at safety rules
        # or at everything said before is not.
        "instruction_override",
        rf"\b{_OVERRIDE_VERB}\b[^.\n]{{0,30}}\b((safety|security|moderation) {_INSTRUCTIONS}"
        rf"|{_INSTRUCTIONS} de (securite|moderation))\b",
    ),
    (
        "instruction_override",
        r"\b(forget|oublie[rsz]?|ignore[rsz]?) (everything|all) (you were|you've been|that was)"
        r"|\b(oublie[rsz]?|ignore[rsz]?) tout ce (qu'on t'a|que je t'ai|qui precede|qui a ete)",
    ),
    ("role_reassignment", r"^\W*(system|systeme|admin|developer|developpeur)\s*:"),
    (
        "role_reassignment",
        r"\b(you are now|from now on,? you|tu es desormais|vous etes desormais"
        r"|a partir de maintenant,? (tu|vous) (es|etes|vas|allez|reponds|repondez))\b",
    ),
    ("role_reassignment", r"\b(new|nouvelles?) (instructions?|consignes?|directives?)\s*:"),
    (
        "jailbreak",
        r"\b(do anything now|developer mode|mode developpeur|jailbreak mode|mode jailbreak"
        r"|dan mode|mode dan|god mode|mode dieu)\b",
    ),
    (
        "jailbreak",
        r"\b(without|sans) (any |aucune? |the )?(restrictions?|filters?|filtres?|limits?"
        r"|limites?|censure|censorship|garde-fous?|guardrails?)\b[^.\n]{0,60}"
        r"\b(answer|reponds?|repondez|respond|tell|dis|explain|explique)",
    ),
    (
        "jailbreak",
        r"\b(no longer bound|not bound by|n'es plus (tenu|soumis|lie)|n'etes plus (tenus?|soumis))",
    ),
    (
        "jailbreak",
        r"\b(freed from|free of|liberee? de|debarrassee? de) (its|their|your|ses|leurs|tes) "
        r"(guardrails|garde-fous|filters|filtres|restrictions|rules|regles|limits|limites)",
    ),
    (
        "system_prompt_leak",
        r"\b(reveal|print|show|repeat|display|output|dump|leak|give me|tell me|recite|translate"
        r"|revele|affiche|repete|montre|donne|recopie|divulgue|traduis)\b[^.\n]{0,40}"
        r"\b(system prompt|initial prompt|hidden (instructions|prompt)"
        r"|your (\w+ )?(instructions|prompt|rules|configuration)"
        r"|(the )?(text|instructions) above|prompt systeme|prompt initial"
        r"|instructions? (systeme|initiales|cachees)|(tes|vos) (instructions|consignes|regles)"
        r"|(ta|votre) (\w+ )?configuration|texte ci-dessus"
        r"|texte (qui se trouve |situe |place )?avant (cette|ce) (question|message)"
        r"|(everything|all|tout ce qui) (that )?(was |a ete |est )?(written|ecrit)"
        r" (before|above|avant|au-dessus))",
    ),
    (
        "indirect_marker",
        r"(note (to|for) the (ai|assistant|model|llm)|note (pour|a) l'(ia|assistant|agent)"
        r"|\b(p\.?s\.?) (for|to|pour|a) (the |l')?(ai|ia|assistant|model|modele)\b"
        r"|if you are an? (ai|assistant|language model)|si tu es une? (ia|assistant|modele)"
        r"|a l'attention (de l'ia|de l'assistant|du modele)"
        r"|\[(system|systeme|instructions?)\]|<\s*(system|instructions?)\s*>"
        r"|\b(the assistant|l'assistant) (forgets|ignores|must|reveals|shows|oublie|ignore|doit"
        r"|revele|affiche)\b"
        r"|assistant,? (ignore|oublie|reponds|tu dois)|ai (assistant|model),? (ignore|you must))",
    ),
    (
        "tool_abuse",
        r"\b(call|invoke|run|execute|trigger|use|appelle|lance|declenche|utilise)\b"
        r"[^.\n]{0,30}\b(tool|function|outil|fonction|commande|api|endpoint)\b[^.\n]{0,60}"
        r"\b(delete|drop|export|send|transfer|wire|disable|supprim\w*|envoi\w*|export\w*"
        r"|transfer\w*|desactiv\w*|vire\w*|purge\w*)",
    ),
    (
        "tool_abuse",
        r"(rm -rf|drop table|truncate table|;\s*--|curl\s+-|wget\s+https?:|os\.system"
        r"|subprocess|/etc/passwd|delete from \w+)",
    ),
)

_PII_RULES: tuple[tuple[str, str], ...] = (
    ("pii_email", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    ("pii_iban", r"\b[a-z]{2}\d{2}(?: ?[a-z0-9]{4}){3,7}(?: ?[a-z0-9]{1,3})?\b"),
    ("pii_phone", r"(?<!\d)(?:\+33 ?|0)[1-9](?:[ .-]?\d{2}){4}(?!\d)"),
)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

_COMPILED = tuple((label, re.compile(pattern)) for label, pattern in RULES + _PII_RULES)


def fold(text: str) -> str:
    """Lower-case and drop accents so one pattern matches "règles", "Règles" and "regles"."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def find_labels(text: str) -> tuple[str, ...]:
    folded = fold(text)
    labels = {label for label, pattern in _COMPILED if pattern.search(folded)}
    # A bare 16-digit run is often a reference number; Luhn keeps those out.
    for match in _CARD.finditer(folded):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            labels.add("pii_card")
    return tuple(sorted(labels))


class RegexGuard(Guard):
    name = "regex"
    covers = frozenset(
        {
            "direct_injection",
            "indirect_injection",
            "jailbreak",
            "system_prompt_leak",
            "tool_abuse",
            "pii",
        }
    )

    def check(self, text: str) -> Verdict:
        labels = find_labels(text)
        return Verdict(flagged=bool(labels), labels=labels, score=1.0 if labels else 0.0)
