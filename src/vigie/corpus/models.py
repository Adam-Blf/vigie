"""The unit the rest of the pipeline indexes, retrieves and cites."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ChunkKind = Literal["article", "annex", "recital"]


class Chunk(BaseModel):
    """One citable piece of a regulation.

    `article` holds the number as printed ("28", "III" for an annex) so a citation such as
    "[DORA art. 28 §1]" can be rebuilt without guessing. `eid` follows the ELI anchors used
    on EUR-Lex, which lets the interface deep-link to the exact place in the official text.
    """

    model_config = ConfigDict(frozen=True)

    regulation: str
    celex: str
    kind: ChunkKind
    article: str
    paragraph: str | None
    title: str
    chapter: str
    text: str
    url: str
    eid: str
    retrieved_on: str
