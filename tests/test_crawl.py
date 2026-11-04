from collections.abc import Iterator, Sequence
from pathlib import Path

from cerebro.adapters.jsonl_pages import JsonlPageStore
from cerebro.application.crawl import crawl
from cerebro.domain.pages import Category, PageRef, RawPage
from cerebro.ports.wiki import WikiSource

CATEGORY = Category.CHARACTERS


def page(pageid: int) -> RawPage:
    return RawPage(pageid, f"Page {pageid}", pageid * 10, "2026-11-02T00:00:00Z", "")


class FakeWiki(WikiSource):
    """A wiki whose category lists `listed`; only ids in `existing` can be fetched."""

    batch_limit = 2

    def __init__(self, listed: list[int], existing: list[int] | None = None) -> None:
        self.listed = listed
        if existing is None:
            existing = listed
        self.pages = {i: page(i) for i in existing}

        # What the crawl asked for, so tests can check it.
        self.title_requests = 0
        self.fetched: list[int] = []
        self.batch_sizes: list[int] = []

    def category_titles(self, category: Category) -> Iterator[PageRef]:
        self.title_requests += 1
        yield from (PageRef(i, f"Page {i}") for i in self.listed)

    def fetch(self, pageids: Sequence[int]) -> list[RawPage]:
        self.batch_sizes.append(len(pageids))
        self.fetched.extend(pageids)
        return [self.pages[i] for i in pageids if i in self.pages]


def test_first_crawl_saves_every_listed_page_in_batches(tmp_path: Path) -> None:
    wiki = FakeWiki(listed=[1, 2, 3, 4, 5])
    store = JsonlPageStore(tmp_path)

    report = crawl(wiki, store, CATEGORY)

    assert store.saved_ids(CATEGORY) == {1, 2, 3, 4, 5}
    assert max(wiki.batch_sizes) <= wiki.batch_limit
    assert report.fetched == 5


def test_interrupted_crawl_resumes_without_refetching_or_relisting(
    tmp_path: Path,
) -> None:
    wiki = FakeWiki(listed=[1, 2, 3, 4, 5])
    store = JsonlPageStore(tmp_path)

    crawl(wiki, store, CATEGORY, limit=2)  # stops early, like a Ctrl-C
    second = crawl(wiki, store, CATEGORY)
    third = crawl(wiki, store, CATEGORY)

    assert sorted(wiki.fetched) == [1, 2, 3, 4, 5]  # each page fetched exactly once
    assert wiki.title_requests == 1
    assert (second.already_saved, second.fetched) == (2, 3)
    assert third.fetched == 0


def test_listed_pages_the_wiki_no_longer_has_are_reported_missing(
    tmp_path: Path,
) -> None:
    wiki = FakeWiki(listed=[1, 2, 3], existing=[1, 3])
    store = JsonlPageStore(tmp_path)

    report = crawl(wiki, store, CATEGORY)

    assert store.saved_ids(CATEGORY) == {1, 3}
    assert (report.fetched, report.missing) == (2, 1)
