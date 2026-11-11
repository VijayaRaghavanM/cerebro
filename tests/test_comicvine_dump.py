import json
from pathlib import Path

from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.domain.comicvine import (
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)


def write_lines(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_characters_come_with_their_issues(tmp_path: Path) -> None:
    # Made-up rows in the download's shape; real Comic Vine data never goes in tests.
    write_lines(
        tmp_path / "characters.jsonl",
        [
            {
                "id": 1,
                "name": "Weather Witch",
                "real_name": "Ann Doe",
                "aliases": "Stormcaller\r\n  The Witch \n\n",
                "count_of_issue_appearances": 12,
            },
            {
                "id": 2,
                "name": "Nobody",
                "real_name": "None",
                "aliases": None,
                "count_of_issue_appearances": 0,
            },
        ],
    )
    write_lines(
        tmp_path / "character-issues.jsonl",
        [{"id": 1, "name": "Weather Witch", "issue_ids": [11, 10, 99]}],
    )
    write_lines(
        tmp_path / "issues.jsonl",
        [
            {
                "id": 10,
                "issue_number": "3",
                "cover_date": "1951-05-01",
                "volume": {"id": 5, "name": "Strange Tales"},
            },
            {
                "id": 11,
                "issue_number": "4",
                "cover_date": None,
                "volume": {"id": 5, "name": "Strange Tales"},
            },
        ],
    )

    characters = list(ComicVineDump(tmp_path).characters())

    assert characters == [
        # Issue 99 isn't in the download, so it drops out of the list.
        ComicVineCharacter(
            id=1,
            name="Weather Witch",
            real_name="Ann Doe",
            aliases=("Stormcaller", "The Witch"),
            appearances=12,
            detail=ComicVineDetail(
                issues=(
                    ComicVineIssue("Strange Tales", "4", cover_date=None),
                    ComicVineIssue("Strange Tales", "3", cover_date="1951-05-01"),
                ),
            ),
        ),
        # No detail was downloaded for it, and "None" means no real name.
        ComicVineCharacter(
            id=2,
            name="Nobody",
            real_name=None,
            aliases=(),
            appearances=0,
            detail=None,
        ),
    ]
