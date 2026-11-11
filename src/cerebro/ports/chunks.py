"""Where chunks are kept for a search to read."""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from cerebro.domain.chunks import Chunk


class ChunkStore(ABC):
    @abstractmethod
    def replace_chunks(self, chunks: Iterable[Chunk]) -> None:
        """Make `chunks` the stored chunks, all at once."""
