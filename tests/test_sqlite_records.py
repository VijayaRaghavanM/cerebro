import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from helpers import (
    real_character,
    real_comic,
    real_team,
    rows,
)

from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.domain.pages import Category
from cerebro.domain.records import Record


def test_a_record_is_stored_with_its_links_and_categories(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    record = real_character()

    SqliteRecordStore(path).replace(Category.CHARACTERS, [record])

    assert rows(path, "SELECT pageid, name, height FROM characters") == [
        (record.pageid, "Daniel Berkhart", "5'10\"")
    ]
    links = rows(path, "SELECT field, title, text FROM links WHERE kind = 'characters'")
    assert links == [(link.field, link.title, link.text) for link in record.links]
    categories = rows(
        path, "SELECT name FROM categories WHERE pageid = ?", record.pageid
    )
    assert [name for (name,) in categories] == list(record.categories)


def test_a_comics_stories_get_rows_of_their_own(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    record = real_comic()

    # Twice, as a rerun would: the second run replaces the first run's stories.
    SqliteRecordStore(path).replace(Category.COMICS, [record])
    SqliteRecordStore(path).replace(Category.COMICS, [record])

    stories = rows(path, "SELECT pageid, number, title, writers FROM stories")
    assert len(stories) == 4
    pageid, number, title, writers = stories[0]
    assert (pageid, number) == (record.pageid, 1)
    assert title == record.stories[0].title
    assert json.loads(str(writers)) == ["Len Kaminski", "Scott Benson"]
    cover_artists = rows(path, "SELECT cover_artists FROM comics")[0][0]
    assert json.loads(str(cover_artists)) == list(record.cover_artists)

    # A story's links say which story they are in; the issue's own links don't.
    story_links = rows(path, "SELECT title FROM links WHERE story = 2")
    assert ("Suzi Endo (Earth-616)",) in story_links
    issue_links = rows(path, "SELECT title FROM links WHERE story IS NULL")
    assert issue_links == [(link.title,) for link in record.links]


def test_replacing_a_category_leaves_the_others(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace(Category.CHARACTERS, [real_character()])
    store.replace(Category.TEAMS, [real_team()])

    store.replace(Category.CHARACTERS, [])

    path = store.path
    assert rows(path, "SELECT * FROM links WHERE kind = 'characters'") == []
    assert rows(path, "SELECT name FROM teams") == [("Livewires",)]
    assert len(rows(path, "SELECT * FROM links WHERE kind = 'teams'")) == len(
        real_team().links
    )


def test_a_failed_run_keeps_the_previous_records(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace(Category.CHARACTERS, [real_character()])

    def records_then_failure() -> Iterator[Record]:
        yield real_character()
        raise RuntimeError("the parser crashed")

    with pytest.raises(RuntimeError):
        store.replace(Category.CHARACTERS, records_then_failure())

    path = store.path
    assert rows(path, "SELECT name FROM characters") == [("Daniel Berkhart",)]
    assert len(rows(path, "SELECT * FROM links")) == len(real_character().links)


def test_characters_read_back_as_they_were_stored(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    berkhart = real_character()
    # Another character with a lower page id, one of the links and no categories.
    other = replace(
        berkhart,
        pageid=1,
        title="Someone (Earth-616)",
        categories=(),
        links=berkhart.links[:1],
    )

    store.replace(Category.CHARACTERS, [berkhart, other])

    assert list(store.characters()) == [other, berkhart]


def test_comics_read_back_as_they_were_stored(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    # The fixture page has no categories of its own.
    issue = replace(real_comic(), categories=("Marvel Comics Presents Vol 1",))
    # Another comic with a lower page id, one of the links and no stories.
    other = replace(
        issue,
        pageid=1,
        title="Someone Vol 1 1",
        stories=(),
        categories=(),
        links=issue.links[:1],
    )

    store.replace(Category.COMICS, [issue, other])

    assert list(store.comics()) == [other, issue]
