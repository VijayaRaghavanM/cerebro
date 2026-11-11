"""Records in a SQLite file, where the agent's tools can query them."""

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_origin

from cerebro.domain.pages import Category
from cerebro.domain.records import Character, Comic, Link, Record
from cerebro.ports.records import RecordReader, RecordStore

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

# Fields stored in tables of their own rather than in a column.
ROW_FIELDS_LEFT_OUT = {"links", "categories", "stories"}


class SqliteRecordStore(RecordStore, RecordReader):
    """Records in one SQLite file.

    Each category has a table named after it, with a column per record field, and a
    comic's stories are in `stories`. Every record's links are in `links` and its
    categories in `categories`, keyed by category and page id, so they can be queried
    across kinds: which records link to X-Men (Earth-616)? Lists of names, such as a
    story's writers, are JSON arrays.
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
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute("SELECT * FROM characters ORDER BY pageid"):
                yield _from_columns(
                    Character,
                    row,
                    categories=_categories_of(db, "characters", row["pageid"]),
                    links=_links_of(db, "characters", row["pageid"]),
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


def _links_of(db: sqlite3.Connection, kind: str, pageid: int) -> tuple[Link, ...]:
    rows = db.execute(
        "SELECT field, title, text FROM links"
        " WHERE kind = ? AND pageid = ? AND story IS NULL ORDER BY rowid",
        (kind, pageid),
    )
    return tuple(Link(field, title, text) for field, title, text in rows)
