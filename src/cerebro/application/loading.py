"""Load Comic Vine's characters into the record store."""

from collections.abc import Iterator
from dataclasses import dataclass

from cerebro.domain.comicvine import ComicVineCharacter
from cerebro.ports.comicvine import ComicVineSource, ComicVineStore


@dataclass(frozen=True)
class LoadReport:
    characters: int
    with_detail: int  # of those, the ones the download fetched in detail


def load_comicvine(source: ComicVineSource, store: ComicVineStore) -> LoadReport:
    """Replace the stored Comic Vine characters with the source's.

    Characters stream through one at a time, so they are never held in memory whole.
    """
    characters = with_detail = 0

    def stream() -> Iterator[ComicVineCharacter]:
        nonlocal characters, with_detail
        for character in source.characters():
            characters += 1
            if character.detail is not None:
                with_detail += 1
            yield character

    store.replace_comicvine(stream())

    return LoadReport(characters=characters, with_detail=with_detail)
