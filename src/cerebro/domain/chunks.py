"""Chunks: the pieces of a page that a search ranks and an answer cites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """One piece of a page that a search can rank and an answer can cite.

    `id` is "<pageid>:<revid>:<number>", stable for a revision. `section` names
    where on the page the text sits, such as "History > Early Life". `prefix` is
    situating text for search, kept apart from `text` so every prefix arm uses
    the same chunks and ids.
    """

    id: str
    pageid: int
    revid: int
    number: int  # from 0, in page order
    title: str
    section: str
    prefix: str
    text: str


@dataclass(frozen=True)
class ChunkHit:
    """A chunk a search found, with the search's score for it (higher is better)."""

    chunk: Chunk
    score: float
