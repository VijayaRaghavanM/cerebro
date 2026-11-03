from pathlib import Path

from cerebro.adapters.raw_pages import RawPageStore
from cerebro.domain.pages import PageRef, RawPage


def page(pageid: int) -> RawPage:
    return RawPage(
        pageid=pageid,
        title=f"Page {pageid}",
        revid=pageid * 10,
        timestamp="2026-11-02T00:00:00Z",
        wikitext="{{Marvel Database:Character Template}}",
    )


def test_pages_appended_in_one_run_are_read_back_in_the_next(tmp_path: Path) -> None:
    RawPageStore(tmp_path, "characters").append([page(1), page(2)])
    RawPageStore(tmp_path, "characters").append([page(3)])

    store = RawPageStore(tmp_path, "characters")
    assert list(store.read()) == [page(1), page(2), page(3)]
    assert store.saved_ids() == {1, 2, 3}


def test_titles_are_none_until_saved_then_read_back(tmp_path: Path) -> None:
    store = RawPageStore(tmp_path, "teams")
    assert store.load_titles() is None

    refs = [PageRef(pageid=1, title="X-Men"), PageRef(pageid=2, title="Avengers")]
    store.save_titles(refs)
    assert RawPageStore(tmp_path, "teams").load_titles() == refs
