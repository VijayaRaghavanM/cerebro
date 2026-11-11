import json
from dataclasses import replace
from pathlib import Path

from helpers import comicvine_characters, real_character, rows

from cerebro.adapters.sqlite_comicvine import SqliteComicVineStore
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.domain.comicvine import CharacterMatch
from cerebro.domain.pages import Category


def test_a_new_set_of_matches_replaces_the_old_one(tmp_path: Path) -> None:
    store = SqliteComicVineStore(tmp_path / "records.sqlite")
    store.replace_matches([CharacterMatch(1, 10, 0.5), CharacterMatch(2, 20, 0.25)])

    # Two Comic Vine entries can be the same Fandom page.
    store.replace_matches([CharacterMatch(3, 30, 0.5), CharacterMatch(3, 31, 0.75)])

    stored = rows(
        store.path,
        "SELECT pageid, comicvine_id, overlap FROM comicvine_matches ORDER BY rowid",
    )
    assert stored == [(3, 30, 0.5), (3, 31, 0.75)]


def test_comic_vine_characters_are_stored_with_their_detail(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"

    SqliteComicVineStore(path).replace_comicvine(comicvine_characters())

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
    SqliteComicVineStore(path).replace_comicvine(comicvine_characters()[1:])

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
    store = SqliteComicVineStore(path)
    store.replace_comicvine(comicvine_characters())

    store.replace_comicvine(comicvine_characters()[1:])

    assert rows(path, "SELECT id FROM comicvine_characters") == [(2,)]


def test_matched_characters_are_ranked_by_appearances(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    records = SqliteRecordStore(path)
    store = SqliteComicVineStore(path)
    berkhart = real_character()
    other = replace(berkhart, pageid=1, title="Someone (Earth-616)")
    records.replace(Category.CHARACTERS, [berkhart, other])
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
