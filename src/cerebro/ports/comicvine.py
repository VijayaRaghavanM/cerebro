"""What matching needs from Comic Vine, and where the matches go."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from cerebro.domain.comicvine import CharacterMatch, ComicVineCharacter


class ComicVineSource(ABC):
    @abstractmethod
    def characters(self) -> Iterator[ComicVineCharacter]:
        """Every Marvel character Comic Vine lists, one at a time."""


class MatchStore(ABC):
    @abstractmethod
    def replace_matches(self, matches: Iterable[CharacterMatch]) -> None:
        """Make `matches` the stored matches, all at once."""
