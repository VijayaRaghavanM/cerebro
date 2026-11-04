"""What the crawler needs from a wiki."""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence

from cerebro.domain.pages import PageRef, RawPage


class WikiUnavailable(Exception):
    """The wiki kept failing after every retry."""


class WikiSource(ABC):
    """Both methods raise WikiUnavailable when the wiki keeps failing."""

    @abstractmethod
    def category_titles(self, category: str) -> Iterator[PageRef]:
        """Every page in the category, in the wiki's order."""

    @abstractmethod
    def fetch(self, pageids: Sequence[int]) -> list[RawPage]:
        """The latest revision of each page. Pages that no longer exist are left out."""
