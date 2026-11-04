from pathlib import Path

from cerebro.adapters.raw_pages import JsonlPageStore
from cerebro.domain.pages import Category, PageRef, RawPage


def page(pageid: int) -> RawPage:
    return RawPage(
        pageid=pageid,
        title=f"Page {pageid}",
        revid=pageid * 10,
        timestamp="2026-11-02T00:00:00Z",
        wikitext="{{Marvel Database:Character Template}}",
    )


def test_pages_appended_in_one_run_are_read_back_in_the_next(tmp_path: Path) -> None:
    JsonlPageStore(tmp_path).append(Category.CHARACTERS, [page(1), page(2)])
    JsonlPageStore(tmp_path).append(Category.CHARACTERS, [page(3)])

    store = JsonlPageStore(tmp_path)
    assert list(store.read(Category.CHARACTERS)) == [page(1), page(2), page(3)]
    assert store.saved_ids(Category.CHARACTERS) == {1, 2, 3}


def test_titles_are_none_until_saved_then_read_back(tmp_path: Path) -> None:
    store = JsonlPageStore(tmp_path)
    assert store.load_titles(Category.TEAMS) is None

    refs = [PageRef(pageid=1, title="X-Men"), PageRef(pageid=2, title="Avengers")]
    store.save_titles(Category.TEAMS, refs)
    assert JsonlPageStore(tmp_path).load_titles(Category.TEAMS) == refs


def test_each_category_has_its_own_files(tmp_path: Path) -> None:
    store = JsonlPageStore(tmp_path)
    store.append(Category.CHARACTERS, [page(1)])
    store.save_titles(Category.TEAMS, [PageRef(pageid=2, title="X-Men")])

    assert store.saved_ids(Category.TEAMS) == set()
    assert store.load_titles(Category.CHARACTERS) is None

    # The names the existing dumps use, so a rerun finds them instead of starting over.
    names = sorted(path.name for path in tmp_path.iterdir())
    assert names == ["characters.jsonl", "teams-titles.json"]
