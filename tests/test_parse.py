from collections.abc import Iterable, Iterator
from dataclasses import fields

from cerebro.application.parse import ParseReport, parse
from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Record, Team
from cerebro.ports.pages import PageReader
from cerebro.ports.records import RecordParser, RecordStore

CATEGORY = Category.TEAMS


def page(pageid: int, wikitext: str) -> RawPage:
    return RawPage(
        pageid, f"Page {pageid}", pageid * 10, "2026-11-02T00:00:00Z", wikitext
    )


def team(pageid: int) -> Team:
    """A team record with only its page and name filled."""
    texts = {field.name: None for field in fields(Team) if field.type == str | None}
    return Team(
        pageid=pageid,
        title=f"Page {pageid}",
        revid=pageid * 10,
        name=f"Page {pageid}",
        categories=(),
        links=(),
        **texts,
    )


class FakePages(PageReader):
    def __init__(self, pages: list[RawPage]) -> None:
        self.pages = pages

    def read(self, category: Category) -> Iterator[RawPage]:
        yield from self.pages


class FakeParser(RecordParser):
    """Finds a team on pages whose wikitext says "team", and nothing on others."""

    def parse(self, page: RawPage) -> Record | None:
        return team(page.pageid) if page.wikitext == "team" else None


class FakeStore(RecordStore):
    def __init__(self) -> None:
        self.records: dict[Category, list[Record]] = {}

    def replace(self, category: Category, records: Iterable[Record]) -> None:
        self.records[category] = list(records)


def test_stores_the_record_of_every_page_that_holds_one() -> None:
    pages = FakePages([page(1, "team"), page(2, "a list"), page(3, "team")])
    store = FakeStore()

    report = parse(pages, FakeParser(), store, CATEGORY)

    assert store.records[CATEGORY] == [team(1), team(3)]
    assert report == ParseReport(pages=3, records=2)


def test_reports_progress_page_by_page() -> None:
    pages = FakePages([page(1, "team"), page(2, "a list"), page(3, "team")])
    done: list[int] = []

    parse(pages, FakeParser(), FakeStore(), CATEGORY, progress=done.append)

    assert done == [1, 2, 3]
