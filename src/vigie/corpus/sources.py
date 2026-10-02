"""Registry of the regulations Vigie answers on.

The short code is what users read in a citation, so it is the French usage (RGPD, not GDPR).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from vigie.config import Settings


@dataclass(frozen=True)
class Regulation:
    code: str
    celex: str
    title: str


REGULATIONS: tuple[Regulation, ...] = (
    Regulation(
        "DORA",
        "32022R2554",
        "Règlement (UE) 2022/2554 sur la résilience opérationnelle numérique du secteur financier",
    ),
    Regulation(
        "AIACT",
        "32024R1689",
        "Règlement (UE) 2024/1689 établissant des règles harmonisées concernant l'intelligence "
        "artificielle",
    ),
    Regulation(
        "RGPD",
        "32016R0679",
        "Règlement (UE) 2016/679 relatif à la protection des données à caractère personnel",
    ),
    Regulation(
        "AMLR",
        "32024R1624",
        "Règlement (UE) 2024/1624 relatif à la prévention de l'utilisation du système financier "
        "aux fins du blanchiment de capitaux ou du financement du terrorisme",
    ),
)


def get_regulation(code: str) -> Regulation:
    for regulation in REGULATIONS:
        if regulation.code == code.upper():
            return regulation
    known = ", ".join(r.code for r in REGULATIONS)
    raise KeyError(f"unknown regulation {code!r}, expected one of {known}")


def cellar_url(regulation: Regulation, settings: Settings) -> str:
    return f"{settings.cellar_base_url}{regulation.celex}"


def eurlex_url(regulation: Regulation, settings: Settings, eid: str | None = None) -> str:
    """Public link shown next to a citation, anchored on the article when we know it."""
    url = f"{settings.eurlex_base_url}{regulation.celex}"
    return f"{url}#{quote(eid, safe='_.')}" if eid else url
