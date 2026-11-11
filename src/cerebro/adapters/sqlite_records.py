"""Records in a SQLite file, where the agent's tools can query them."""

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing
from dataclasses import Field, asdict, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_origin

from cerebro.domain.comicvine import (
    CharacterMatch,
    ComicVineCharacter,
    ComicVineDetail,
)
from cerebro.domain.pages import Category
from cerebro.domain.records import Character, Comic, Link, Record, Story
from cerebro.ports.comicvine import ComicVineStore, MatchStore
from cerebro.ports.records import RecordReader, RecordsMissing, RecordStore

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

SHARED_TABLES = [
    "CREATE TABLE IF NOT EXISTS links "
    "(kind TEXT, pageid INTEGER, story INTEGER, field TEXT, title TEXT, text TEXT)",
    "CREATE INDEX IF NOT EXISTS links_by_title ON links (title)",
    "CREATE INDEX IF NOT EXISTS links_by_record ON links (kind, pageid)",
    "CREATE TABLE IF NOT EXISTS categories (kind TEXT, pageid INTEGER, name TEXT)",
    "CREATE INDEX IF NOT EXISTS categories_by_name ON categories (name)",
    "CREATE INDEX IF NOT EXISTS categories_by_record ON categories (kind, pageid)",
]

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

# Fields stored in tables of their own rather than in a column.
ROW_FIELDS_LEFT_OUT = {"links", "categories", "stories"}


class SqliteRecordStore(RecordStore, RecordReader, MatchStore, ComicVineStore):
    """Records in one SQLite file.

    Each category has a table named after it, with a column per record field, and a
    comic's stories are in `stories`. Every record's links are in `links` and its
    categories in `categories`, keyed by category and page id, so they can be queried
    across kinds: which records link to X-Men (Earth-616)? Lists of names, such as a
    story's writers, are JSON arrays. `comicvine_characters` holds what Comic Vine says
    of each character, `comicvine_matches` pairs its ids with character pages, and the
    view `character_ranking` lists the matched characters by Comic Vine appearances.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    # Writing: a whole category at a time.

    def replace(self, category: Category, records: Iterable[Record]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # autocommit=False keeps every statement in the transaction, the DROP TABLE
        # included; by default sqlite3 runs that outside one.
        with closing(sqlite3.connect(self.path, autocommit=False)) as db:
            # One transaction: it commits when every record is in, and rolls back if
            # anything fails, which leaves the previous records in place.
            with db:
                for statement in SHARED_TABLES:
                    db.execute(statement)
                self._clear(db, category)
                created: set[str] = set()
                for record in records:
                    self._insert(db, category, record, created)

    # Reading: one record at a time, so a category is never held in memory whole.

    def characters(self) -> Iterator[Character]:
        if not self._stored("characters"):
            raise RecordsMissing("No characters are stored yet")

        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute("SELECT * FROM characters ORDER BY pageid"):
                yield _from_columns(
                    Character,
                    row,
                    categories=_categories_of(db, "characters", row["pageid"]),
                    links=_links_of(db, "characters", row["pageid"], story=None),
                )

    def comics(self) -> Iterator[Comic]:
        if not self._stored("comics"):
            raise RecordsMissing("No comics are stored yet")

        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute("SELECT * FROM comics ORDER BY pageid"):
                pageid = row["pageid"]
                story_rows = db.execute(
                    "SELECT * FROM stories WHERE pageid = ? ORDER BY number", (pageid,)
                )
                stories = tuple(
                    _from_columns(
                        Story,
                        story,
                        links=_links_of(db, "comics", pageid, story=story["number"]),
                    )
                    for story in story_rows
                )

                yield _from_columns(
                    Comic,
                    row,
                    stories=stories,
                    categories=_categories_of(db, "comics", pageid),
                    links=_links_of(db, "comics", pageid, story=None),
                )

    def _stored(self, table: str) -> bool:
        # Checked before connecting, which would create an empty file.
        if not self.path.exists():
            return False
        with closing(sqlite3.connect(self.path)) as db:
            found = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            )
            return found.fetchone() is not None

    # Matches to Comic Vine, replaced all at once like a category.

    def replace_matches(self, matches: Iterable[CharacterMatch]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [(m.comicvine_id, m.pageid, m.overlap) for m in matches]

        with closing(sqlite3.connect(self.path, autocommit=False)) as db:
            with db:
                db.execute("DROP TABLE IF EXISTS comicvine_matches")
                # Keyed by Comic Vine id: two Comic Vine entries can be one Fandom page.
                db.execute(
                    "CREATE TABLE comicvine_matches"
                    " (comicvine_id INTEGER PRIMARY KEY, pageid INTEGER, overlap REAL)"
                )
                db.executemany("INSERT INTO comicvine_matches VALUES (?, ?, ?)", rows)

    # Comic Vine's characters, replaced all at once like the matches.

    def replace_comicvine(self, characters: Iterable[ComicVineCharacter]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        columns = _comicvine_columns()
        marks = ", ".join("?" for _ in columns)

        with closing(sqlite3.connect(self.path, autocommit=False)) as db:
            with db:
                db.execute("DROP TABLE IF EXISTS comicvine_characters")
                db.execute(f"CREATE TABLE comicvine_characters ({', '.join(columns)})")
                # Recreated, not kept, so a changed definition takes effect on rerun.
                db.execute("DROP VIEW IF EXISTS character_ranking")
                db.execute(CHARACTER_RANKING)
                for character in characters:
                    values = _comicvine_values(character)
                    db.execute(
                        f"INSERT INTO comicvine_characters VALUES ({marks})", values
                    )

    # Writing, step by step.

    def _clear(self, db: sqlite3.Connection, category: Category) -> None:
        # Dropped, not emptied, so a table follows the record type when fields change.
        db.execute(f'DROP TABLE IF EXISTS "{category}"')
        if category is Category.COMICS:
            db.execute("DROP TABLE IF EXISTS stories")
        db.execute("DELETE FROM links WHERE kind = ?", (str(category),))
        db.execute("DELETE FROM categories WHERE kind = ?", (str(category),))

    def _insert(
        self,
        db: sqlite3.Connection,
        category: Category,
        record: Record,
        created: set[str],
    ) -> None:
        kind = str(category)
        _insert_row(db, kind, ("pageid",), _columns(record), created)
        db.executemany(
            "INSERT INTO categories VALUES (?, ?, ?)",
            [(kind, record.pageid, name) for name in record.categories],
        )
        _insert_links(db, kind, record.pageid, None, record.links)

        if isinstance(record, Comic):
            for story in record.stories:
                row = {"pageid": record.pageid, **_columns(story)}
                _insert_row(db, "stories", ("pageid", "number"), row, created)
                _insert_links(db, kind, record.pageid, story.number, story.links)


def _columns(item: Any) -> dict[str, Any]:
    """A record's fields as column values, with nested credits spread into columns."""
    row: dict[str, Any] = {}
    for field in fields(item):
        value = getattr(item, field.name)
        if field.name in ROW_FIELDS_LEFT_OUT:
            continue
        if is_dataclass(value):
            row |= _columns(value)
        elif isinstance(value, tuple):
            row[field.name] = json.dumps(value, ensure_ascii=False)
        else:
            row[field.name] = value
    return row


def _character_fields() -> list[Field[Any]]:
    return [f for f in fields(ComicVineCharacter) if f.name != "detail"]


def _detail_fields() -> list[Field[Any]]:
    # The issue lists stay in the download; Fandom's cast lists cover them.
    return [f for f in fields(ComicVineDetail) if f.name != "issues"]


def _comicvine_columns() -> list[str]:
    """Column definitions from the types, so they don't depend on the first row."""
    columns = []
    for field in _character_fields() + _detail_fields():
        kind = "INTEGER" if field.type is int else "TEXT"
        key = " PRIMARY KEY" if field.name == "id" else ""
        columns.append(f"{field.name} {kind}{key}")
    return columns


def _comicvine_values(character: ComicVineCharacter) -> list[Any]:
    values = [_cell(getattr(character, f.name)) for f in _character_fields()]

    # NULL when there is no detail, so "not fetched" differs from an empty list.
    detail = character.detail
    for field in _detail_fields():
        values.append(None if detail is None else _cell(getattr(detail, field.name)))
    return values


def _cell(value: Any) -> Any:
    """A column value: lists as JSON, a died-in issue as an object of its fields."""
    if isinstance(value, tuple):
        return json.dumps(value, ensure_ascii=False, default=asdict)
    return value


def _from_columns[T: DataclassInstance](
    cls: type[T], row: sqlite3.Row, **left_out: Any
) -> T:
    """The reverse of `_columns`: an item rebuilt from its row.

    `left_out` gives the fields kept in tables of their own, such as `links`.
    """
    values: dict[str, Any] = {}
    for field in fields(cls):
        if field.name in ROW_FIELDS_LEFT_OUT:
            continue
        if isinstance(field.type, type) and is_dataclass(field.type):
            values[field.name] = _from_columns(field.type, row)
        elif get_origin(field.type) is tuple:
            values[field.name] = tuple(json.loads(row[field.name]))
        else:
            values[field.name] = row[field.name]
    return cls(**values, **left_out)


def _insert_row(
    db: sqlite3.Connection,
    table: str,
    key: tuple[str, ...],
    row: dict[str, Any],
    created: set[str],
) -> None:
    if table not in created:
        columns = [
            f'"{name}" {"INTEGER" if isinstance(value, int) else "TEXT"}'
            for name, value in row.items()
        ]
        primary_key = ", ".join(f'"{name}"' for name in key)
        db.execute(
            f'CREATE TABLE "{table}" ({", ".join(columns)}, '
            f"PRIMARY KEY ({primary_key}))"
        )
        created.add(table)

    names = ", ".join(f'"{name}"' for name in row)
    marks = ", ".join("?" for _ in row)
    db.execute(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', list(row.values()))


def _insert_links(
    db: sqlite3.Connection,
    kind: str,
    pageid: int,
    story: int | None,
    links: tuple[Link, ...],
) -> None:
    db.executemany(
        "INSERT INTO links VALUES (?, ?, ?, ?, ?, ?)",
        [(kind, pageid, story, link.field, link.title, link.text) for link in links],
    )


def _categories_of(db: sqlite3.Connection, kind: str, pageid: int) -> tuple[str, ...]:
    rows = db.execute(
        "SELECT name FROM categories WHERE kind = ? AND pageid = ? ORDER BY rowid",
        (kind, pageid),
    )
    return tuple(name for (name,) in rows)


def _links_of(
    db: sqlite3.Connection, kind: str, pageid: int, *, story: int | None
) -> tuple[Link, ...]:
    """A record's own links when `story` is None, else the links in that story."""
    # IS matches a None story to the NULL on a record's own links; = would match none.
    rows = db.execute(
        "SELECT field, title, text FROM links"
        " WHERE kind = ? AND pageid = ? AND story IS ? ORDER BY rowid",
        (kind, pageid, story),
    )
    return tuple(Link(field, title, text) for field, title, text in rows)
