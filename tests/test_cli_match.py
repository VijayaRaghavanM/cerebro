import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cerebro.adapters.fandom_wikitext import parse_character, parse_comic
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.domain.pages import Category, RawPage
from cerebro.domain.records import Character, Comic, Link, Record
from cerebro.interfaces.cli import app

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The real settings, pointed at a temp folder the way a user would point them."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def fixture(name: str) -> RawPage:
    return RawPage(**json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def berkhart() -> Character:
    record = parse_character(fixture("daniel_berkhart.json"))
    assert record is not None
    return record


def issue_with_berkhart() -> Comic:
    """Marvel Comics Presents #170 (1994), with Berkhart added to its first story."""
    record = parse_comic(fixture("marvel_comics_presents_170.json"))
    assert record is not None
    first = record.stories[0]
    cast = (*first.links, Link("appearing", berkhart().title, "Mysterio"))
    return replace(record, stories=(replace(first, links=cast), *record.stories[1:]))


def store(data_dir: Path, *categories: Category) -> None:
    records: dict[Category, list[Record]] = {
        Category.CHARACTERS: [berkhart()],
        Category.COMICS: [issue_with_berkhart()],
    }
    for category in categories:
        SqliteRecordStore(data_dir / "records.sqlite").replace(
            category, records[category]
        )


def write_comicvine(data_dir: Path) -> None:
    # Made-up rows in the download's shape; real Comic Vine data never goes in tests.
    folder = data_dir / "raw" / "comicvine"
    folder.mkdir(parents=True)
    mysterio = {
        "id": 1,
        "name": "Mysterio",
        "real_name": "Daniel Berkhart",
        "aliases": None,
        "count_of_issue_appearances": 40,
    }
    # Listed, but with no issue list downloaded.
    nobody = {"id": 2, "name": "Nobody", "count_of_issue_appearances": 1}
    rows = {
        "characters.jsonl": [mysterio, nobody],
        "character-issues.jsonl": [{"id": 1, "name": "Mysterio", "issue_ids": [7]}],
        "issues.jsonl": [
            {
                "id": 7,
                "issue_number": "170",
                "cover_date": "1994-12-01",
                "volume": {"id": 3, "name": "Marvel Comics Presents"},
            }
        ],
    }
    for name, lines in rows.items():
        text = "".join(json.dumps(line) + "\n" for line in lines)
        (folder / name).write_text(text, encoding="utf-8")


def test_match_comicvine_stores_the_matches(data_dir: Path) -> None:
    store(data_dir, Category.CHARACTERS, Category.COMICS)
    write_comicvine(data_dir)

    result = CliRunner().invoke(app, ["match", "comicvine"])

    assert result.exit_code == 0
    assert result.output == (
        "1 of the 1 Comic Vine characters with an issue list matched "
        "(2 listed in all; 0 pages claimed twice)\n"
    )
    with sqlite3.connect(data_dir / "records.sqlite") as db:
        matches = db.execute("SELECT comicvine_id, pageid FROM comicvine_matches")
        assert matches.fetchall() == [(1, berkhart().pageid)]


def test_matching_before_parsing_says_what_to_run(data_dir: Path) -> None:
    write_comicvine(data_dir)

    result = CliRunner().invoke(app, ["match", "comicvine"])

    assert result.exit_code == 1
    assert "No characters are stored yet. Run `cerebro parse fandom`" in result.output
    # Checking for records doesn't leave an empty database behind.
    assert not (data_dir / "records.sqlite").exists()


def test_matching_before_comics_are_parsed_says_what_to_run(data_dir: Path) -> None:
    store(data_dir, Category.CHARACTERS)
    write_comicvine(data_dir)

    result = CliRunner().invoke(app, ["match", "comicvine"])

    assert result.exit_code == 1
    assert "No comics are stored yet. Run `cerebro parse fandom`" in result.output


def test_matching_without_comic_vine_data_says_which_file_is_missing(
    data_dir: Path,
) -> None:
    store(data_dir, Category.CHARACTERS, Category.COMICS)

    result = CliRunner().invoke(app, ["match", "comicvine"])

    assert result.exit_code == 1
    assert "issues.jsonl is missing" in result.output
