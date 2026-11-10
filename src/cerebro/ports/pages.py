"""Raw pages between runs: where the crawler keeps them and where parsing reads them."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from cerebro.domain.pages import Category, PageRef, RawPage


class PageStore(ABC):
    """Raw pages: wikitext exactly as the wiki returned it, before any parsing.

    Parsing turns these pages into records, which are stored separately.
    """

    @abstractmethod
    def load_titles(self, category: Category) -> list[PageRef] | None:
        """The category's saved titles, or None if they were never saved."""

    @abstractmethod
    def save_titles(self, category: Category, refs: Iterable[PageRef]) -> None:
        """Save the category's titles, so later runs don't ask the wiki again."""

    @abstractmethod
    def saved_ids(self, category: Category) -> set[int]:
        """Ids of the pages saved so far."""

    @abstractmethod
    def append(self, category: Category, pages: Iterable[RawPage]) -> None:
        """Save pages after the ones already saved, without rewriting those."""


class PageReader(ABC):
    """Saved raw pages, read back for parsing."""

    @abstractmethod
    def read(self, category: Category) -> Iterator[RawPage]:
        """Every saved page in the category, one at a time, in the order saved."""
