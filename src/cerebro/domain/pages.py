"""Raw wiki pages as fetched, before any parsing."""

from dataclasses import dataclass
from enum import StrEnum


class Category(StrEnum):
    """The wiki categories Cerebro collects pages from."""

    CHARACTERS = "characters"
    TEAMS = "teams"
    COMICS = "comics"


@dataclass(frozen=True)
class PageRef:
    """A page listed in a wiki category."""

    pageid: int
    title: str


@dataclass(frozen=True)
class RawPage:
    """The latest revision of one page, exactly as the wiki returned it."""

    pageid: int
    title: str
    revid: int
    timestamp: str
    wikitext: str
