"""Chunk search that combines other searches."""

import re

from cerebro.domain.chunks import Chunk, ChunkHit
from cerebro.ports.chunks import ChunkSearch

# How many chunks each search offers the fusion. A chunk one search ranks low can
# still win if another ranks it high, so the lists are taken deep.
CANDIDATES = 100

# Added to a rank before it is inverted, so the first place counts only a little
# more than the second and agreement between searches outweighs one search's
# favourite. 60 is the value from the paper that introduced the method.
RANK_OFFSET = 60


class FusedSearch(ChunkSearch):
    """Ranks chunks by reciprocal rank fusion: a chunk scores 1 / (offset + rank) in
    each search that found it, and the scores add up. The searches' own scores are
    never compared, so a keyword score and a cosine need no common scale.
    """

    def __init__(self, searches: list[ChunkSearch]) -> None:
        self.searches = searches

    def search(self, query: str, limit: int) -> list[ChunkHit]:
        chunks: dict[str, Chunk] = {}
        scores: dict[str, float] = {}
        for search in self.searches:
            hits = search.search(query, CANDIDATES)
            for rank, hit in enumerate(hits, start=1):
                chunk_id = hit.chunk.id
                chunks.setdefault(chunk_id, hit.chunk)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RANK_OFFSET + rank)

        # A dict keeps the order its keys first appeared in, and a sort keeps equal
        # scores in their order: a tie goes to the chunk found first.
        ranked = sorted(scores, key=lambda chunk_id: -scores[chunk_id])

        top = ranked[:limit]
        return [ChunkHit(chunks[chunk_id], scores[chunk_id]) for chunk_id in top]


# A character page's title ends with its reality, as in "Ororo Munroe (Earth-616)"
# or "Rogue (Mojomedia) (Mojoverse)"; a comic page's title names no reality.
MAIN_REALITY = "(Earth-616)"
TRAILING_PARENTHETICAL = re.compile(r"\([^()]+\)\s*$")
# A query that names a reality wants that reality's pages, so it keeps its ranking.
NAMES_A_REALITY = re.compile(r"\bearth-|\bultimate\b|\bmcu\b", re.IGNORECASE)


class MainRealityFirst(ChunkSearch):
    """Passages from main-reality character pages come first, taking turns with comic
    passages, then every other reality's, each group in the order the search ranked
    it. Alternate realities share a character's text almost word for word, so a plain
    ranking serves them as often as the main page."""

    def __init__(self, search: ChunkSearch) -> None:
        self.inner = search

    def search(self, query: str, limit: int) -> list[ChunkHit]:
        if NAMES_A_REALITY.search(query):
            return self.inner.search(query, limit)

        hits = self.inner.search(query, CANDIDATES)

        # Turns, not one list: synopses that repeat a name hundreds of times would
        # push the character's own page out of the results.
        groups: dict[str, list[ChunkHit]] = {"main": [], "comic": [], "other": []}
        for hit in hits:
            groups[_page_kind(hit.chunk.title)].append(hit)

        ranked = [*_take_turns(groups["main"], groups["comic"]), *groups["other"]]
        return ranked[:limit]


def _page_kind(title: str) -> str:
    """The page's kind: "main" for a main-reality character page, "comic" for a comic
    page, whose title names no reality, and "other" for any other reality's page."""
    ending = TRAILING_PARENTHETICAL.search(title)
    if ending is None:
        return "comic"
    return "main" if ending[0] == MAIN_REALITY else "other"


def _take_turns(first: list[ChunkHit], second: list[ChunkHit]) -> list[ChunkHit]:
    """One from each list in turn, starting with `first`, then the longer one's rest."""
    turns = [hit for pair in zip(first, second, strict=False) for hit in pair]
    shorter = min(len(first), len(second))
    return turns + first[shorter:] + second[shorter:]
