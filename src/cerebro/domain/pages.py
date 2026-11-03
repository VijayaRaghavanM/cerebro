"""Raw wiki pages as fetched, before any parsing."""

from dataclasses import dataclass


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
