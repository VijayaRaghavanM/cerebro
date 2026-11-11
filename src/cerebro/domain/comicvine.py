"""Comic Vine's characters, and the Fandom pages they match."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ComicVineIssue:
    """An issue as Comic Vine describes it, with Comic Vine's volume as `series`."""

    series: str
    number: str
    cover_date: str | None  # ISO, as in "1963-03-01"


@dataclass(frozen=True)
class ComicVineDetail:
    """What Comic Vine gives for a character fetched in detail."""

    issues: tuple[ComicVineIssue, ...]


@dataclass(frozen=True)
class ComicVineCharacter:
    id: int
    name: str
    real_name: str | None
    aliases: tuple[str, ...]
    appearances: int  # issues it appears in, by Comic Vine's count
    # None when the download has no detail for it.
    detail: ComicVineDetail | None


@dataclass(frozen=True)
class CharacterMatch:
    """A Fandom character page and the Comic Vine character it is."""

    pageid: int
    comicvine_id: int
    overlap: float  # how far their issues coincide, from 0 (none) to 1 (all)
