"""What matching needs from Comic Vine."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from cerebro.domain.comicvine import ComicVineCharacter


class ComicVineSource(ABC):
    @abstractmethod
    def characters(self) -> Iterator[ComicVineCharacter]:
        """Every Marvel character Comic Vine lists, one at a time."""
