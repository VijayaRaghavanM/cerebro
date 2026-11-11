"""Comic Vine's characters, as its downloaded data describes them."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ComicVineIssue:
    """An issue as Comic Vine describes it, with Comic Vine's volume as `series`."""

    series: str
    number: str
    cover_date: str | None  # ISO, as in "1963-03-01"


@dataclass(frozen=True)
class ComicVineCharacter:
    id: int
    name: str
    real_name: str | None
    aliases: tuple[str, ...]
    appearances: int  # issues it appears in, by Comic Vine's count
    # The issues it appears in, or None when the download has no list for it.
    issues: tuple[ComicVineIssue, ...] | None
