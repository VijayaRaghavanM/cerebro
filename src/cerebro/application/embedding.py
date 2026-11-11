"""Embed every chunk, in parts that a stopped run keeps."""

from collections.abc import Callable
from dataclasses import dataclass
from itertools import batched

from cerebro.ports.chunks import ChunkReader
from cerebro.ports.embeddings import Embedder, VectorStore

# A part is a few minutes of work, so a stopped run loses little.
PART_SIZE = 10_000

# Measured fastest on the home server: 140 chunks a second against 48 at 32.
BATCH_SIZE = 128


@dataclass(frozen=True)
class EmbedReport:
    chunks: int
    parts: int
    skipped_parts: int  # of those, the ones an earlier run had finished


def embed_chunks(
    chunks: ChunkReader,
    embedder: Embedder,
    store: VectorStore,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> EmbedReport:
    """Embed each chunk's text and save the vectors, part by part.

    A part the store already has is skipped, so a rerun resumes where a run stopped.
    A part is saved only when all of it is embedded.
    """
    # A first pass to count, so progress can show a total. It is one cheap read of
    # the chunk table, next to about an hour of embedding.
    total = sum(1 for _ in chunks.chunks())
    parts = skipped_parts = done = 0

    for number, part in enumerate(batched(chunks.chunks(), PART_SIZE, strict=False)):
        parts += 1

        if store.has_part(number):
            skipped_parts += 1
            done += len(part)
            if progress:
                progress(done, total)
            continue

        vectors: list[list[float]] = []
        for batch in batched(part, BATCH_SIZE, strict=False):
            vectors.extend(embedder.embed_documents([chunk.text for chunk in batch]))
            done += len(batch)
            if progress:
                progress(done, total)

        store.save_part(number, [chunk.id for chunk in part], vectors)

    return EmbedReport(chunks=total, parts=parts, skipped_parts=skipped_parts)
