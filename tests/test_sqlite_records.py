import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from helpers import (
    comicvine_characters,
    real_character,
    real_comic,
    real_team,
)

from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application.chunking import chunk_character
from cerebro.domain.chunks import Chunk
from cerebro.domain.comicvine import (
    CharacterMatch,
)
from cerebro.domain.pages import Category
from cerebro.domain.records import Record
from cerebro.ports.records import RecordsMissing


def rows(path: Path, sql: str, *params: object) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as db:
        return db.execute(sql, params).fetchall()


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
    berkhart = real_character()
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


def test_chunks_are_stored_and_a_rerun_replaces_them(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    store = SqliteRecordStore(path)
    chunks = chunk_character(real_character())
    assert len(chunks) > 1

    store.replace_chunks(chunks)
    store.replace_chunks(chunks[:1])

    stored = rows(path, "SELECT id, pageid, revid, number, title FROM chunks")
    first = chunks[0]
    assert stored == [(first.id, first.pageid, first.revid, 0, first.title)]


def made_up_chunks(*texts: str) -> list[Chunk]:
    return [
        Chunk(f"1:7:{n}", 1, 7, n, "Ann Doe (Earth-1)", "History", text)
        for n, text in enumerate(texts)
    ]


def test_a_chunk_with_a_rare_word_ranks_above_ones_with_common_words(
    tmp_path: Path,
) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(
        made_up_chunks(
            "She has great power.",
            "Her power grew.",
            "Power runs in the family.",
            "She built a telescope.",
        )
    )

    hits = store.search("power telescope", limit=4)

    assert len(hits) == 4
    assert hits[0].chunk.number == 3
    assert hits[0].score > hits[1].score > 0


def test_a_search_finds_other_forms_of_a_word(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She has many powers.", "She likes tea."))

    hits = store.search("power", limit=5)

    assert [hit.chunk.number for hit in hits] == [0]


def test_hits_come_best_first(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    # The best match is stored in the middle, so neither id order is the score order.
    texts = (
        "Claws and a long walk by the river with friends.",
        "Wolverine has claws, Wolverine heals.",
        "A long walk by the river.",
    )
    store.replace_chunks(made_up_chunks(*texts))

    hits = store.search("Wolverine claws walk", limit=5)

    assert [hit.chunk.number for hit in hits] == [1, 0, 2]
    assert [hit.score for hit in hits] == sorted(
        (hit.score for hit in hits), reverse=True
    )


def test_a_possessive_finds_the_name(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("Wolverine has claws.", "She likes tea."))

    hits = store.search("What is Wolverine's real name?", limit=5)

    assert [hit.chunk.number for hit in hits] == [0]


def test_a_search_ignores_diacritics(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("Her name is Xuân.", "She likes tea."))

    hits = store.search("Xuan", limit=5)

    assert [hit.chunk.number for hit in hits] == [0]


def test_a_search_reads_syntax_characters_as_text(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She said hello.", "Spider-Man swung."))

    hits = store.search('"hello" * title: (Spider-Man NOT', limit=5)

    assert {hit.chunk.number for hit in hits} == {0, 1}


def test_a_search_returns_no_more_than_the_limit(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("storm one", "storm two", "storm three"))

    assert len(store.search("storm", limit=2)) == 2


def test_a_search_returns_the_chunk_as_it_was_stored(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    chunks = made_up_chunks("She has many powers.")
    store.replace_chunks(chunks)

    assert [hit.chunk for hit in store.search("powers", limit=1)] == chunks


def test_a_rerun_rebuilds_the_search_index(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She has a telescope."))

    store.replace_chunks(made_up_chunks("She has a cape."))

    assert store.search("telescope", limit=5) == []
    assert len(store.search("cape", limit=5)) == 1


def test_a_search_with_no_words_finds_nothing(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She has a telescope."))

    assert store.search("?! ... *", limit=5) == []


def test_searching_before_chunks_are_stored_says_so(tmp_path: Path) -> None:
    store = SqliteRecordStore(tmp_path / "records.sqlite")
    store.replace(Category.CHARACTERS, [real_character()])

    with pytest.raises(RecordsMissing):
        store.search("telescope", limit=5)


def test_every_chunk_gets_a_row_with_its_own_id(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    chunks = chunk_character(real_character())

    SqliteRecordStore(path).replace_chunks(chunks)

    stored = rows(path, "SELECT id, section, text FROM chunks ORDER BY number")
    assert stored == [(c.id, c.section, c.text) for c in chunks]
    assert len({id for id, _, _ in stored}) == len(chunks)
