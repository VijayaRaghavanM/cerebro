import json
from pathlib import Path

import pytest

from cerebro.adapters.comicvine_dump import ComicVineDump
from cerebro.domain.comicvine import (
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
    DownloadPart,
)


def write_lines(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def named(*names: str) -> list[dict[str, object]]:
    """Linked records as the download lists them, each with an id and a name."""
    return [{"id": n, "name": name} for n, name in enumerate(names, start=1)]


def test_characters_come_with_their_detail(tmp_path: Path) -> None:
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
                "site_detail_url": "https://comicvine.example/witch/4005-1/",
            },
            {
                "id": 2,
                "name": "Nobody",
                "real_name": "None",
                "aliases": None,
                "count_of_issue_appearances": 0,
                "site_detail_url": "https://comicvine.example/nobody/4005-2/",
            },
            {
                "id": 3,
                "name": "Blank",
                "count_of_issue_appearances": 1,
                "site_detail_url": "https://comicvine.example/blank/4005-3/",
            },
        ],
    )
    write_lines(
        tmp_path / "character-issues.jsonl",
        [
            {
                "id": 1,
                "name": "Weather Witch",
                "issue_ids": [11, 10, 99],
                "deck": "Controls the weather.",
                "birth": "March 3",
                "gender": 2,
                "origin": {"id": 4, "name": "Mutant"},
                # An entry without a name is skipped; the rest keep their order.
                "powers": [*named("Flight", "Lightning"), {"id": 9}],
                "creators": named("Ann Artist"),
                "teams": named("Storm Watch", "Sky Club"),
                "team_friends": named("Cloud Nine"),
                "team_enemies": named("Dry Spell"),
                "character_friends": named("Gale"),
                "character_enemies": named("Drought"),
                "volume_credits": named("Strange Tales", "Weather Weekly"),
                "movies": named("The Storm"),
                # Resolved by id: an empty name still counts, and 99 isn't downloaded.
                "issues_died_in": [
                    {"id": 10, "name": "Last Rites"},
                    {"id": 11, "name": ""},
                    {"id": 99, "name": "Lost Issue"},
                ],
                "story_arc_credits": named("Rain Check"),
                "date_last_updated": "2020-01-02 03:04:05",
            },
            {
                "id": 3,
                "name": "Blank",
                "issue_ids": [],
                "deck": "None",
                "gender": None,
                "origin": None,
                "powers": None,
                "date_last_updated": None,
            },
        ],
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
            url="https://comicvine.example/witch/4005-1/",
            detail=ComicVineDetail(
                issues=(
                    ComicVineIssue("Strange Tales", "4", cover_date=None),
                    ComicVineIssue("Strange Tales", "3", cover_date="1951-05-01"),
                ),
                deck="Controls the weather.",
                birth="March 3",
                gender="female",
                origin="Mutant",
                powers=("Flight", "Lightning"),
                creators=("Ann Artist",),
                teams=("Storm Watch", "Sky Club"),
                team_friends=("Cloud Nine",),
                team_enemies=("Dry Spell",),
                friends=("Gale",),
                enemies=("Drought",),
                volumes=("Strange Tales", "Weather Weekly"),
                movies=("The Storm",),
                died_in=(
                    ComicVineIssue("Strange Tales", "3", cover_date="1951-05-01"),
                    ComicVineIssue("Strange Tales", "4", cover_date=None),
                ),
                story_arcs=("Rain Check",),
                updated="2020-01-02 03:04:05",
            ),
        ),
        # No detail was downloaded for it, and "None" means no real name.
        ComicVineCharacter(
            id=2,
            name="Nobody",
            real_name=None,
            aliases=(),
            appearances=0,
            url="https://comicvine.example/nobody/4005-2/",
            detail=None,
        ),
        # Detail with every field empty, missing or the text "None".
        ComicVineCharacter(
            id=3,
            name="Blank",
            real_name=None,
            aliases=(),
            appearances=1,
            url="https://comicvine.example/blank/4005-3/",
            detail=ComicVineDetail(
                issues=(),
                deck=None,
                birth=None,
                gender=None,
                origin=None,
                powers=(),
                creators=(),
                teams=(),
                team_friends=(),
                team_enemies=(),
                friends=(),
                enemies=(),
                volumes=(),
                movies=(),
                died_in=(),
                story_arcs=(),
                updated=None,
            ),
        ),
    ]


@pytest.mark.parametrize(
    ("code", "gender"),
    [(1, "male"), (2, "female"), (0, "other"), (3, None), (None, None)],
)
def test_gender_codes_are_read_as_words(
    tmp_path: Path, code: int | None, gender: str | None
) -> None:
    write_lines(
        tmp_path / "characters.jsonl",
        [
            {
                "id": 1,
                "name": "Weather Witch",
                "site_detail_url": "https://comicvine.example/witch/4005-1/",
            }
        ],
    )
    write_lines(
        tmp_path / "character-issues.jsonl",
        [{"id": 1, "issue_ids": [], "gender": code}],
    )
    write_lines(tmp_path / "issues.jsonl", [])

    [character] = ComicVineDump(tmp_path).characters()

    assert character.detail is not None
    assert character.detail.gender == gender


def test_appending_keeps_earlier_records(tmp_path: Path) -> None:
    dump = ComicVineDump(tmp_path / "download")

    dump.append(DownloadPart.ISSUES, [{"id": 10, "issue_number": "1"}])
    dump.append(DownloadPart.ISSUES, [{"id": 11, "issue_number": "2"}, {"id": 12}])

    assert [record["id"] for record in dump.read(DownloadPart.ISSUES)] == [10, 11, 12]
    assert dump.saved_ids(DownloadPart.ISSUES) == {10, 11, 12}
    # Other parts are separate files.
    assert dump.saved_ids(DownloadPart.DETAILS) == set()


def test_a_part_never_written_is_empty(tmp_path: Path) -> None:
    dump = ComicVineDump(tmp_path)

    assert list(dump.read(DownloadPart.CHARACTERS)) == []
    assert dump.saved_ids(DownloadPart.CHARACTERS) == set()


def test_records_are_written_one_per_line(tmp_path: Path) -> None:
    record = {"id": 1, "name": "Weather Witch"}

    ComicVineDump(tmp_path).append(DownloadPart.CHARACTERS, [record])

    lines = (tmp_path / "characters.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines == [json.dumps(record)]


def test_the_marvel_list_is_none_until_saved(tmp_path: Path) -> None:
    dump = ComicVineDump(tmp_path / "download")
    marvel = [{"id": 1, "name": "Weather Witch"}, {"id": 2, "name": "Nobody"}]

    assert dump.load_marvel_characters() is None

    dump.save_marvel_characters(marvel)

    assert dump.load_marvel_characters() == marvel


def test_a_crawled_download_reads_back_as_characters(tmp_path: Path) -> None:
    dump = ComicVineDump(tmp_path)

    dump.append(
        DownloadPart.CHARACTERS,
        [
            {
                "id": 1,
                "name": "Weather Witch",
                "real_name": "Ann Doe",
                "aliases": "Stormcaller",
                "count_of_issue_appearances": 2,
                "site_detail_url": "https://comicvine.example/witch/4005-1/",
            }
        ],
    )
    dump.append(
        DownloadPart.DETAILS,
        [
            {
                "id": 1,
                "issue_ids": [10, 11],
                "gender": 2,
                "powers": named("Flight"),
                "issues_died_in": [{"id": 11, "name": "Last Rites"}],
            }
        ],
    )
    dump.append(
        DownloadPart.ISSUES,
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

    [character] = dump.characters()

    assert character.name == "Weather Witch"
    assert character.aliases == ("Stormcaller",)
    assert character.detail is not None
    assert character.detail.powers == ("Flight",)
    assert character.detail.gender == "female"
    assert character.detail.issues == (
        ComicVineIssue("Strange Tales", "3", cover_date="1951-05-01"),
        ComicVineIssue("Strange Tales", "4", cover_date=None),
    )
    assert character.detail.died_in == (
        ComicVineIssue("Strange Tales", "4", cover_date=None),
    )
