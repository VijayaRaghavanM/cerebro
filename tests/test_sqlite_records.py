import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from cerebro.adapters.fandom_wikitext import parse_character, parse_comic, parse_team
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.domain.comicvine import (
    CharacterMatch,
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Character, Comic, Record, Team

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


def fixture(name: str) -> RawPage:
    return RawPage(**json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def character() -> Character:
    record = parse_character(fixture("daniel_berkhart.json"))
    assert record is not None
    return record


def team() -> Team:
    record = parse_team(fixture("livewires.json"))
    assert record is not None
    return record


def comic() -> Comic:
    record = parse_comic(fixture("marvel_comics_presents_170.json"))
    assert record is not None
    return record


def rows(path: Path, sql: str, *params: object) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as db:
        return db.execute(sql, params).fetchall()


def test_a_record_is_stored_with_its_links_and_categories(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    record = character()

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
    record = comic()

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
    store.replace(Category.CHARACTERS, [character()])
    store.replace(Category.TEAMS, [team()])

    store.replace(Category.CHARACTERS, [])

    path = store.path
    assert rows(path, "SELECT * FROM links WHERE kind = 'characters'") == []
    assert rows(path, "SELECT name FROM teams") == [("Livewires",)]
    assert len(rows(path, "SELECT * FROM links WHERE kind = 'teams'")) == len(
        team().links
    )


def test_a_failed_run_keeps_the_previous_records(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace(Category.CHARACTERS, [character()])

    def records_then_failure() -> Iterator[Record]:
        yield character()
        raise RuntimeError("the parser crashed")

    with pytest.raises(RuntimeError):
        store.replace(Category.CHARACTERS, records_then_failure())

    path = store.path
    assert rows(path, "SELECT name FROM characters") == [("Daniel Berkhart",)]
    assert len(rows(path, "SELECT * FROM links")) == len(character().links)


def test_characters_read_back_as_they_were_stored(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    berkhart = character()
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
    issue = replace(comic(), categories=("Marvel Comics Presents Vol 1",))
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


def test_a_new_set_of_matches_replaces_the_old_one(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_matches([CharacterMatch(1, 10, 0.5), CharacterMatch(2, 20, 0.25)])

    # Two Comic Vine entries can be the same Fandom page.
    store.replace_matches([CharacterMatch(3, 30, 0.5), CharacterMatch(3, 31, 0.75)])

    stored = rows(
        store.path,
        "SELECT pageid, comicvine_id, overlap FROM comicvine_matches ORDER BY rowid",
    )
    assert stored == [(3, 30, 0.5), (3, 31, 0.75)]


def comicvine_characters() -> list[ComicVineCharacter]:
    """Made-up characters: one fetched in detail, one only listed."""
    detail = ComicVineDetail(
        issues=(ComicVineIssue("Strange Tales", "3", "1951-05-01"),),
        deck="Controls the weather.",
        birth=None,
        gender="female",
        origin="Mutant",
        powers=("Flight", "Lightning"),
        creators=(),
        teams=("Storm Watch",),
        team_friends=(),
        team_enemies=(),
        friends=(),
        enemies=(),
        volumes=("Strange Tales",),
        movies=(),
        died_in=(ComicVineIssue("Strange Tales", "4", None),),
        story_arcs=(),
        updated="2020-01-02 03:04:05",
    )
    witch = ComicVineCharacter(
        1,
        "Weather Witch",
        "Ann Doe",
        ("Stormcaller",),
        12,
        "https://cv.example/1",
        detail,
    )
    nobody = ComicVineCharacter(2, "Nobody", None, (), 0, "https://cv.example/2", None)
    return [witch, nobody]


def test_comic_vine_characters_are_stored_with_their_detail(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"

    SqliteRecordStore(path).replace_comicvine(comicvine_characters())

    witch, nobody = rows(
        path,
        "SELECT id, name, real_name, aliases, appearances, url, deck, birth, gender,"
        " powers, creators, died_in, updated, issues"
        " FROM comicvine_characters ORDER BY id",
    )
    assert witch[:6] == (
        1,
        "Weather Witch",
        "Ann Doe",
        '["Stormcaller"]',
        12,
        "https://cv.example/1",
    )
    assert witch[6:11] == (
        "Controls the weather.",
        None,
        "female",
        '["Flight", "Lightning"]',
        "[]",
    )
    assert json.loads(str(witch[11])) == [
        {"series": "Strange Tales", "number": "4", "cover_date": None}
    ]
    assert witch[12] == "2020-01-02 03:04:05"
    assert json.loads(str(witch[13])) == [
        {"series": "Strange Tales", "number": "3", "cover_date": "1951-05-01"}
    ]
    # Not fetched in detail: NULL, which is not the empty list of a fetched one.
    assert nobody[6:] == (None,) * 8
    assert nobody[3] == "[]"


def test_comic_vine_characters_have_a_column_per_field(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"

    # No row fixes the schema: a character without detail still gets every column.
    SqliteRecordStore(path).replace_comicvine(comicvine_characters()[1:])

    columns = rows(path, "SELECT name FROM pragma_table_info('comicvine_characters')")
    expected = (
        "id name real_name aliases appearances url issues deck birth gender origin "
        "powers "
        "creators teams team_friends team_enemies friends enemies volumes movies "
        "died_in story_arcs updated"
    ).split()
    assert [name for (name,) in columns] == expected


def test_a_new_set_of_comic_vine_characters_replaces_the_old_one(
    tmp_path: Path,
) -> None:
    path = tmp_path / "records.sqlite"
    store = SqliteRecordStore(path)
    store.replace_comicvine(comicvine_characters())

    store.replace_comicvine(comicvine_characters()[1:])

    assert rows(path, "SELECT id FROM comicvine_characters") == [(2,)]


def test_matched_characters_are_ranked_by_appearances(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    store = SqliteRecordStore(path)
    berkhart = character()
    other = replace(berkhart, pageid=1, title="Someone (Earth-616)")
    store.replace(Category.CHARACTERS, [berkhart, other])
    witch, nobody = comicvine_characters()
    # Same appearances as the witch, so only the id orders them.
    twin = replace(nobody, id=3, name="Twin", appearances=12)
    store.replace_comicvine([witch, nobody, twin])
    store.replace_matches(
        [
            CharacterMatch(other.pageid, 1, 0.5),
            CharacterMatch(berkhart.pageid, 2, 0.5),
            CharacterMatch(berkhart.pageid, 3, 0.25),
        ]
    )

    # Again, as a rerun would: the view already exists.
    store.replace_comicvine([witch, nobody, twin])

    assert rows(path, "SELECT * FROM character_ranking ORDER BY rank") == [
        (1, 1, "Someone (Earth-616)", 1, 12),
        (2, berkhart.pageid, berkhart.title, 3, 12),
        (3, berkhart.pageid, berkhart.title, 2, 0),
    ]
