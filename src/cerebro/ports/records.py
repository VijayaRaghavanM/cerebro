"""Records: reading them from pages, keeping them, and reading them back."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Character, Comic, Record


class RecordsMissing(Exception):
    """No records of the kind asked for are stored yet."""


class RecordParser(ABC):
    """Reads one category's records out of raw pages."""

    @abstractmethod
    def parse(self, page: RawPage) -> Record | None:
        """The record on the page, or None if the page holds none of this kind."""


class RecordStore(ABC):
    """Where parsed records are kept for the agent to read."""

    @abstractmethod
    def replace(self, category: Category, records: Iterable[Record]) -> None:
        """Make `records` the category's records, all at once.

        A run that fails partway leaves the category's previous records in place.
        """


class RecordReader(ABC):
    """Stored records, read back."""

    @abstractmethod
    def characters(self) -> Iterator[Character]:
        """Every stored character, with its categories and links, one at a time.

        Raises RecordsMissing if no characters are stored.
        """

    @abstractmethod
    def comics(self) -> Iterator[Comic]:
        """Every stored comic, with its stories, categories and links, one at a time.

        Raises RecordsMissing if no comics are stored.
        """
