"""The Comic Vine download: JSONL files in a folder, written by the crawl."""

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from cerebro.domain.comicvine import (
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
    DownloadPart,
    RawRecord,
)
from cerebro.ports.comicvine import ComicVineSource, DownloadStore

# Comic Vine's gender codes; any other value reads as None.
GENDERS: dict[Any, str] = {0: "other", 1: "male", 2: "female"}

FILES = {
    DownloadPart.CHARACTERS: "characters.jsonl",
    DownloadPart.DETAILS: "character-issues.jsonl",
    DownloadPart.ISSUES: "issues.jsonl",
}


class ComicVineDump(DownloadStore, ComicVineSource):
    """The download's JSONL files in one folder, one object per line.

    The crawl writes it and `cerebro load comicvine` reads it.
    `characters.jsonl` lists every character with its names, appearance count and page.
    `character-issues.jsonl` has the detail of those fetched in detail: issue ids,
    summary, powers, teams and the like. `issues.jsonl` describes those issues.
    `marvel-character-ids.json` is Marvel's character list, saved once.
    Records are only ever appended, so an interrupted crawl resumes where it stopped.
    The download wrote some missing values as the text "None"; they are read as None.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    # Marvel's character list, saved once so reruns skip asking Comic Vine.

    def load_marvel_characters(self) -> list[RawRecord] | None:
        path = self._marvel_path()
        if not path.exists():
            return None

        records: list[RawRecord] = json.loads(path.read_text(encoding="utf-8"))
        return records

    def save_marvel_characters(self, records: Iterable[RawRecord]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._marvel_path().write_text(json.dumps(list(records)), encoding="utf-8")

    # Parts: one JSON object per line, in the order they were fetched.

    def read(self, part: DownloadPart) -> Iterator[RawRecord]:
        if not (self.root / FILES[part]).exists():
            return

        yield from self._rows(part)

    def saved_ids(self, part: DownloadPart) -> set[int]:
        return {int(record["id"]) for record in self.read(part)}

    def append(self, part: DownloadPart, records: Iterable[RawRecord]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

        # Append mode: records already in the file are never rewritten.
        with (self.root / FILES[part]).open("a", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")

    # Characters: the parts joined into the characters the rest of Cerebro reads.

    def characters(self) -> Iterator[ComicVineCharacter]:
        details = self._details()

        for row in self._rows(DownloadPart.CHARACTERS):
            aliases = (_text(row.get("aliases")) or "").splitlines()
            yield ComicVineCharacter(
                id=int(row["id"]),
                name=row["name"],
                real_name=_text(row.get("real_name")),
                aliases=tuple(alias.strip() for alias in aliases if alias.strip()),
                appearances=int(row.get("count_of_issue_appearances") or 0),
                url=row["site_detail_url"],
                detail=details.get(int(row["id"])),
            )

    def _details(self) -> dict[int, ComicVineDetail]:
        """What the download holds for each character fetched in detail, by id.

        An issue the download doesn't describe is left out.
        """
        issues = {
            int(row["id"]): ComicVineIssue(
                series=row["volume"]["name"],
                number=str(row["issue_number"]),
                cover_date=_text(row.get("cover_date")),
            )
            for row in self._rows(DownloadPart.ISSUES)
        }
        details = {}
        for row in self._rows(DownloadPart.DETAILS):
            died_ids = [item["id"] for item in row.get("issues_died_in") or []]
            details[int(row["id"])] = ComicVineDetail(
                issues=_described(row["issue_ids"], issues),
                deck=_text(row.get("deck")),
                birth=_text(row.get("birth")),
                gender=GENDERS.get(row.get("gender")),
                origin=_text((row.get("origin") or {}).get("name")),
                powers=_names(row.get("powers")),
                creators=_names(row.get("creators")),
                teams=_names(row.get("teams")),
                team_friends=_names(row.get("team_friends")),
                team_enemies=_names(row.get("team_enemies")),
                friends=_names(row.get("character_friends")),
                enemies=_names(row.get("character_enemies")),
                volumes=_names(row.get("volume_credits")),
                movies=_names(row.get("movies")),
                died_in=_described(died_ids, issues),
                story_arcs=_names(row.get("story_arc_credits")),
                updated=_text(row.get("date_last_updated")),
            )
        return details

    def _rows(self, part: DownloadPart) -> Iterator[RawRecord]:
        """The part's records; a part missing from the folder is an error."""
        with (self.root / FILES[part]).open(encoding="utf-8") as fh:
            for line in fh:
                yield json.loads(line)

    def _marvel_path(self) -> Path:
        return self.root / "marvel-character-ids.json"


def _described(
    ids: list[int], issues: dict[int, ComicVineIssue]
) -> tuple[ComicVineIssue, ...]:
    """The issues for these ids, in order, leaving out any the download lacks."""
    return tuple(issues[i] for i in ids if i in issues)


def _names(value: Any) -> tuple[str, ...]:
    """The names in a list of linked records, in order; None is an empty list."""
    return tuple(item["name"] for item in value or [] if item.get("name"))


def _text(value: Any) -> str | None:
    """The value as text, or None if it is missing or the text "None"."""
    if value is None or str(value).strip() in ("", "None"):
        return None
    return str(value)
