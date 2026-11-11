"""Comic Vine data downloaded earlier, read from its JSONL files."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cerebro.domain.comicvine import (
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.ports.comicvine import ComicVineSource

# Comic Vine's gender codes; any other value reads as None.
GENDERS: dict[Any, str] = {0: "other", 1: "male", 2: "female"}


class ComicVineDump(ComicVineSource):
    """The download's JSONL files in one folder, one object per line.

    `characters.jsonl` lists every character with its names, appearance count and page.
    `character-issues.jsonl` has the detail of those fetched in detail: issue ids,
    summary, powers, teams and the like. `issues.jsonl` describes those issues.
    The download wrote some missing values as the text "None"; they are read as None.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def characters(self) -> Iterator[ComicVineCharacter]:
        details = self._details()

        for row in self._rows("characters.jsonl"):
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
            for row in self._rows("issues.jsonl")
        }
        details = {}
        for row in self._rows("character-issues.jsonl"):
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

    def _rows(self, name: str) -> Iterator[dict[str, Any]]:
        with (self.root / name).open(encoding="utf-8") as fh:
            for line in fh:
                yield json.loads(line)


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
