"""Where chunks are kept for a search to read."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from cerebro.domain.chunks import Chunk, ChunkHit


class ChunkStore(ABC):
    @abstractmethod
    def replace_chunks(self, chunks: Iterable[Chunk]) -> None:
        """Make `chunks` the stored chunks, all at once."""


class ChunkReader(ABC):
    @abstractmethod
    def chunks(self) -> Iterator[Chunk]:
        """Every stored chunk, in the same order on every call.

        Raises `RecordsMissing` at the call if no chunks are stored.
        """


class ChunkSearch(ABC):
    @abstractmethod
    def search(self, query: str, limit: int) -> list[ChunkHit]:
        """The chunks that best match the query's words, best first.

        Raises `RecordsMissing` if no chunks are stored.
        """
