"""Comic Vine data downloaded earlier, read from its JSONL files."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cerebro.domain.comicvine import ComicVineCharacter, ComicVineIssue
from cerebro.ports.comicvine import ComicVineSource


class ComicVineDump(ComicVineSource):
    """The download's JSONL files in one folder, one object per line.

    `characters.jsonl` lists every character. `character-issues.jsonl` has the issue
    lists of those fetched in detail, and `issues.jsonl` describes their issues.
    The download wrote some missing values as the text "None"; they are read as None.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def characters(self) -> Iterator[ComicVineCharacter]:
        issue_lists = self._issue_lists()

        for row in self._rows("characters.jsonl"):
            aliases = (_text(row.get("aliases")) or "").splitlines()
            yield ComicVineCharacter(
                id=int(row["id"]),
                name=row["name"],
                real_name=_text(row.get("real_name")),
                aliases=tuple(alias.strip() for alias in aliases if alias.strip()),
                appearances=int(row.get("count_of_issue_appearances") or 0),
                issues=issue_lists.get(int(row["id"])),
            )

    def _issue_lists(self) -> dict[int, tuple[ComicVineIssue, ...]]:
        """The issues of each character fetched in detail, by character id.

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
        lists = {}
        for row in self._rows("character-issues.jsonl"):
            ids = row["issue_ids"]
            lists[int(row["id"])] = tuple(issues[i] for i in ids if i in issues)
        return lists

    def _rows(self, name: str) -> Iterator[dict[str, Any]]:
        with (self.root / name).open(encoding="utf-8") as fh:
            for line in fh:
                yield json.loads(line)


def _text(value: Any) -> str | None:
    """The value as text, or None if it is missing or the text "None"."""
    if value is None or str(value).strip() in ("", "None"):
        return None
    return str(value)
