import sqlite3
from pathlib import Path

from helpers import real_character
from typer.testing import CliRunner

from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application.chunking import chunk_character
from cerebro.domain.pages import Category
from cerebro.interfaces.cli import app


def test_chunk_stores_the_chunks_of_the_parsed_characters(data_dir: Path) -> None:
    record = real_character()
    SqliteRecordStore(data_dir / "records.sqlite").replace(
        Category.CHARACTERS, [record]
    )
    expected = chunk_character(record)

    result = CliRunner().invoke(app, ["chunk"])

    assert result.exit_code == 0
    assert result.output == f"1 pages, {len(expected):,} chunks\n"
    with sqlite3.connect(data_dir / "records.sqlite") as db:
        stored = db.execute("SELECT id, text FROM chunks ORDER BY number")
        assert stored.fetchall() == [(c.id, c.text) for c in expected]


def test_chunking_before_parsing_says_what_to_run(data_dir: Path) -> None:
    result = CliRunner().invoke(app, ["chunk"])

    assert result.exit_code == 1
    assert "No characters are stored yet. Run `cerebro parse fandom`" in result.output
