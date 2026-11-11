"""Comic Vine's characters and their matches in the records' SQLite file."""

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import Field, asdict, fields
from pathlib import Path
from typing import Any, get_args, get_origin

from cerebro.adapters.sqlite import has_table, transaction
from cerebro.domain.comicvine import (
    CharacterMatch,
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
from cerebro.ports.comicvine import ComicVineStore, MatchStore

# A view, so the ranking always reflects the latest load and match without copying
# data. The id breaks ties between characters with the same appearances.
CHARACTER_RANKING = (
    "CREATE VIEW character_ranking AS"
    " SELECT ROW_NUMBER() OVER (ORDER BY cv.appearances DESC, cv.id) AS rank,"
    " page.pageid, page.title, cv.id AS comicvine_id, cv.appearances"
    " FROM comicvine_matches m"
    " JOIN comicvine_characters cv ON cv.id = m.comicvine_id"
    " JOIN characters page ON page.pageid = m.pageid"
)


class SqliteComicVineStore(MatchStore, ComicVineStore):
    """Comic Vine's data, in the same SQLite file as the records.

    `comicvine_characters` holds what Comic Vine says of each character,
    `comicvine_matches` pairs its ids with character pages, and the view
    `character_ranking` lists the matched characters by Comic Vine appearances.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    # Matches to Comic Vine, replaced all at once like a category.

    def replace_matches(self, matches: Iterable[CharacterMatch]) -> None:
        rows = [(m.comicvine_id, m.pageid, m.overlap) for m in matches]

        with transaction(self.path) as db:
            db.execute("DROP TABLE IF EXISTS comicvine_matches")
            # Keyed by Comic Vine id: two Comic Vine entries can be one Fandom page.
            db.execute(
                "CREATE TABLE comicvine_matches"
                " (comicvine_id INTEGER PRIMARY KEY, pageid INTEGER, overlap REAL)"
            )
            db.executemany("INSERT INTO comicvine_matches VALUES (?, ?, ?)", rows)

    # Comic Vine's characters, replaced all at once like the matches.

    def replace_comicvine(self, characters: Iterable[ComicVineCharacter]) -> None:
        columns = _comicvine_columns()
        marks = ", ".join("?" for _ in columns)

        with transaction(self.path) as db:
            db.execute("DROP TABLE IF EXISTS comicvine_characters")
            db.execute(f"CREATE TABLE comicvine_characters ({', '.join(columns)})")
            # Recreated, not kept, so a changed definition takes effect on rerun.
            db.execute("DROP VIEW IF EXISTS character_ranking")
            db.execute(CHARACTER_RANKING)
            for character in characters:
                values = _comicvine_values(character)
                db.execute(f"INSERT INTO comicvine_characters VALUES ({marks})", values)

    # Reading: the character matched to a page.

    def character(self, pageid: int) -> ComicVineCharacter | None:
        """The Comic Vine character matched to the page, or None.

        If several are matched, the one whose issues overlap the page's the most.
        """
        # Either table is missing until `cerebro load comicvine` and the match have run.
        if not (
            has_table(self.path, "comicvine_matches")
            and has_table(self.path, "comicvine_characters")
        ):
            return None

        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT cv.* FROM comicvine_matches m"
                " JOIN comicvine_characters cv ON cv.id = m.comicvine_id"
                " WHERE m.pageid = ? ORDER BY m.overlap DESC, cv.id LIMIT 1",
                (pageid,),
            ).fetchone()
        if row is None:
            return None

        return _comicvine_character(row)


def _character_fields() -> list[Field[Any]]:
    return [f for f in fields(ComicVineCharacter) if f.name != "detail"]


def _comicvine_columns() -> list[str]:
    """Column definitions from the types, so they don't depend on the first row."""
    columns = []
    for field in _character_fields() + list(fields(ComicVineDetail)):
        kind = "INTEGER" if field.type is int else "TEXT"
        key = " PRIMARY KEY" if field.name == "id" else ""
        columns.append(f"{field.name} {kind}{key}")
    return columns


def _comicvine_values(character: ComicVineCharacter) -> list[Any]:
    values = [_cell(getattr(character, f.name)) for f in _character_fields()]

    # NULL when there is no detail, so "not fetched" differs from an empty list.
    detail = character.detail
    for field in fields(ComicVineDetail):
        values.append(None if detail is None else _cell(getattr(detail, field.name)))
    return values


def _cell(value: Any) -> Any:
    """A column value: lists as JSON, an issue as an object of its fields."""
    if isinstance(value, tuple):
        return json.dumps(value, ensure_ascii=False, default=asdict)
    return value


def _uncell(field: Field[Any], value: Any) -> Any:
    """The reverse of `_cell`: JSON lists back to tuples, issue objects to issues."""
    if get_origin(field.type) is not tuple:
        return value

    items = json.loads(value)
    if get_args(field.type)[0] is ComicVineIssue:
        return tuple(ComicVineIssue(**item) for item in items)
    return tuple(items)


def _comicvine_character(row: sqlite3.Row) -> ComicVineCharacter:
    values = {f.name: _uncell(f, row[f.name]) for f in _character_fields()}

    # Every detail column is NULL for a character fetched without detail.
    detail = None
    if row["issues"] is not None:
        detail = ComicVineDetail(
            **{f.name: _uncell(f, row[f.name]) for f in fields(ComicVineDetail)}
        )

    return ComicVineCharacter(**values, detail=detail)
