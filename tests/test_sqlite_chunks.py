from pathlib import Path

import pytest
from helpers import real_character, rows

from cerebro.adapters.sqlite_chunks import SqliteChunkIndex
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application.chunking import chunk_character
from cerebro.domain.chunks import Chunk
from cerebro.domain.pages import Category
from cerebro.ports.records import RecordsMissing


def test_chunks_are_stored_and_a_rerun_replaces_them(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    store = SqliteChunkIndex(path)
    chunks = chunk_character(real_character())
    assert len(chunks) > 1

    store.replace_chunks(chunks)
    store.replace_chunks(chunks[:1])

    stored = rows(path, "SELECT id, pageid, revid, number, title FROM chunks")
    first = chunks[0]
    assert stored == [(first.id, first.pageid, first.revid, 0, first.title)]


def made_up_chunks(
    *texts: str, prefix: str = "Ann Doe (Earth-1) > History"
) -> list[Chunk]:
    return [
        Chunk(f"1:7:{n}", 1, 7, n, "Ann Doe (Earth-1)", "History", prefix, text)
        for n, text in enumerate(texts)
    ]


def test_a_search_reads_the_text_not_the_prefix(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(
        made_up_chunks(
            "She has claws.",
            "She likes tea.",
            prefix="Weather Witch (Ann Doe) > Powers",
        )
    )

    assert store.search("Witch", limit=5) == []
    assert [hit.chunk.number for hit in store.search("claws", limit=5)] == [0]


def test_a_chunk_with_a_rare_word_ranks_above_ones_with_common_words(
    tmp_path: Path,
) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
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
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She has many powers.", "She likes tea."))

    hits = store.search("power", limit=5)

    assert [hit.chunk.number for hit in hits] == [0]


def test_hits_come_best_first(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
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
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("Wolverine has claws.", "She likes tea."))

    hits = store.search("What is Wolverine's real name?", limit=5)

    assert [hit.chunk.number for hit in hits] == [0]


def test_a_search_ignores_diacritics(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("Her name is Xuân.", "She likes tea."))

    hits = store.search("Xuan", limit=5)

    assert [hit.chunk.number for hit in hits] == [0]


def test_a_search_reads_syntax_characters_as_text(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She said hello.", "Spider-Man swung."))

    hits = store.search('"hello" * title: (Spider-Man NOT', limit=5)

    assert {hit.chunk.number for hit in hits} == {0, 1}


def test_a_search_returns_no_more_than_the_limit(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("storm one", "storm two", "storm three"))

    assert len(store.search("storm", limit=2)) == 2


def test_a_search_returns_the_chunk_as_it_was_stored(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    chunks = made_up_chunks("She has many powers.")
    store.replace_chunks(chunks)

    assert [hit.chunk for hit in store.search("powers", limit=1)] == chunks


def test_a_rerun_rebuilds_the_search_index(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She has a telescope."))

    store.replace_chunks(made_up_chunks("She has a cape."))

    assert store.search("telescope", limit=5) == []
    assert len(store.search("cape", limit=5)) == 1


def test_a_search_with_no_words_finds_nothing(tmp_path: Path) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    store.replace_chunks(made_up_chunks("She has a telescope."))

    assert store.search("?! ... *", limit=5) == []


def test_searching_before_chunks_are_stored_says_so(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    SqliteRecordStore(path).replace(Category.CHARACTERS, [real_character()])

    with pytest.raises(RecordsMissing):
        SqliteChunkIndex(path).search("telescope", limit=5)


def test_chunks_are_read_back_whole_in_the_order_they_were_stored(
    tmp_path: Path,
) -> None:
    store = SqliteChunkIndex(tmp_path / "records.sqlite")
    chunks = chunk_character(real_character())
    store.replace_chunks(chunks)

    assert list(store.chunks()) == chunks


def test_reading_chunks_before_they_are_stored_says_so(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    SqliteRecordStore(path).replace(Category.CHARACTERS, [real_character()])

    # Raised at the call, not on the first chunk read.
    with pytest.raises(RecordsMissing):
        SqliteChunkIndex(path).chunks()


def test_every_chunk_gets_a_row_with_its_own_id(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    chunks = chunk_character(real_character())

    SqliteChunkIndex(path).replace_chunks(chunks)

    stored = rows(path, "SELECT id, section, text FROM chunks ORDER BY number")
    assert stored == [(c.id, c.section, c.text) for c in chunks]
    assert len({id for id, _, _ in stored}) == len(chunks)
