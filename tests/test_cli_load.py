import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from cerebro.interfaces.cli import app


def write_comicvine(data_dir: Path) -> None:
    # Made-up rows in the download's shape; real Comic Vine data never goes in tests.
    folder = data_dir / "raw" / "comicvine"
    folder.mkdir(parents=True)
    rows = {
        "characters.jsonl": [
            {
                "id": 1,
                "name": "Mysterio",
                "count_of_issue_appearances": 40,
                "site_detail_url": "https://comicvine.example/mysterio/4005-1/",
            },
            # Listed, but not fetched in detail.
            {
                "id": 2,
                "name": "Nobody",
                "count_of_issue_appearances": 1,
                "site_detail_url": "https://comicvine.example/nobody/4005-2/",
            },
        ],
        "character-issues.jsonl": [
            {"id": 1, "issue_ids": [], "deck": "A master of illusion."}
        ],
        "issues.jsonl": [],
    }
    for name, lines in rows.items():
        text = "".join(json.dumps(line) + "\n" for line in lines)
        (folder / name).write_text(text, encoding="utf-8")


def test_load_comicvine_stores_the_characters(data_dir: Path) -> None:
    write_comicvine(data_dir)

    result = CliRunner().invoke(app, ["load", "comicvine"])

    assert result.exit_code == 0
    assert result.output == "2 Comic Vine characters stored, 1 with detail\n"
    with sqlite3.connect(data_dir / "records.sqlite") as db:
        stored = db.execute("SELECT id, name, deck FROM comicvine_characters")
        assert stored.fetchall() == [
            (1, "Mysterio", "A master of illusion."),
            (2, "Nobody", None),
        ]


def test_loading_without_comic_vine_data_says_which_file_is_missing(
    data_dir: Path,
) -> None:
    result = CliRunner().invoke(app, ["load", "comicvine"])

    assert result.exit_code == 1
    assert "issues.jsonl is missing" in result.output
