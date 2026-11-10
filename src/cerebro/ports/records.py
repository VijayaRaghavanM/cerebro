"""What parsing needs: a way to read records from pages, and a place to keep them."""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Record


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
