"""Chunk search by meaning: the chunks whose vectors are nearest the query's."""

from cerebro.domain.chunks import ChunkHit
from cerebro.ports.chunks import ChunkLookup, ChunkSearch
from cerebro.ports.embeddings import Embedder, VectorIndex


class VectorChunkSearch(ChunkSearch):
    def __init__(
        self, embedder: Embedder, vectors: VectorIndex, chunks: ChunkLookup
    ) -> None:
        self.embedder = embedder
        self.vectors = vectors
        self.chunks = chunks

    def search(self, query: str, limit: int) -> list[ChunkHit]:
        query_vector = self.embedder.embed_query(query)
        nearest = self.vectors.nearest(query_vector, limit)

        scores = dict(nearest)
        chunks = self.chunks.chunks_by_id([chunk_id for chunk_id, _ in nearest])

        return [ChunkHit(chunk, scores[chunk.id]) for chunk in chunks]
