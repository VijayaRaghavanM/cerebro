"""What a crawl and matching need from Comic Vine, and where its data and matches go."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Sequence

from cerebro.domain.comicvine import (
    CharacterMatch,
    ComicVineCharacter,
    DownloadPart,
    RawRecord,
)


class ComicVineUnavailable(Exception):
    """Comic Vine kept failing after every retry, or refused a request."""


class ComicVineAPI(ABC):
    """What a crawl needs from Comic Vine. Every method raises ComicVineUnavailable."""

    @property
    @abstractmethod
    def batch_limit(self) -> int:
        """Most ids `character_summaries` and `issues` accept in one call."""

    @abstractmethod
    def marvel_characters(self) -> list[RawRecord]:
        """Every Marvel character, with its id and name."""

    @abstractmethod
    def character_summaries(self, ids: Sequence[int]) -> list[RawRecord]:
        """Name, aliases, appearance count and page url of each character."""

    @abstractmethod
    def character_detail(self, character_id: int) -> RawRecord:
        """Everything kept about one character, with its issues as `issue_ids`."""

    @abstractmethod
    def issues(self, ids: Sequence[int]) -> list[RawRecord]:
        """Number, dates, page url and series (id and name) of each issue."""


class DownloadStore(ABC):
    """Where a crawl keeps what Comic Vine returned, as it returned it."""

    @abstractmethod
    def load_marvel_characters(self) -> list[RawRecord] | None:
        """Marvel's saved character list, or None if it was never saved."""

    @abstractmethod
    def save_marvel_characters(self, records: Iterable[RawRecord]) -> None:
        """Save Marvel's character list, so later runs don't ask Comic Vine again."""

    @abstractmethod
    def read(self, part: DownloadPart) -> Iterator[RawRecord]:
        """Every record saved in the part, one at a time, in the order saved."""

    @abstractmethod
    def saved_ids(self, part: DownloadPart) -> set[int]:
        """Ids of the records saved in the part so far."""

    @abstractmethod
    def append(self, part: DownloadPart, records: Iterable[RawRecord]) -> None:
        """Save records after the ones already in the part, without rewriting those."""


class ComicVineSource(ABC):
    @abstractmethod
    def characters(self) -> Iterator[ComicVineCharacter]:
        """Every Marvel character Comic Vine lists, one at a time."""


class MatchStore(ABC):
    @abstractmethod
    def replace_matches(self, matches: Iterable[CharacterMatch]) -> None:
        """Make `matches` the stored matches, all at once."""


class ComicVineStore(ABC):
    @abstractmethod
    def replace_comicvine(self, characters: Iterable[ComicVineCharacter]) -> None:
        """Make `characters` the stored Comic Vine characters, all at once."""
