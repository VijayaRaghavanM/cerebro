"""Chunk search that combines other searches."""

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
