"""Marvel Database pages as records: the wikitext parser behind RecordParser."""

from collections.abc import Callable

from cerebro.adapters.fandom_wikitext import parse_character, parse_comic, parse_team
from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Record
from cerebro.ports.records import RecordParser

PARSERS: dict[Category, Callable[[RawPage], Record | None]] = {
    Category.CHARACTERS: parse_character,
    Category.TEAMS: parse_team,
    Category.COMICS: parse_comic,
}


class FandomRecordParser(RecordParser):
    """Reads one category's records from Marvel Database wikitext."""

    def __init__(self, category: Category) -> None:
        self._parse = PARSERS[category]

    def parse(self, page: RawPage) -> Record | None:
        return self._parse(page)
