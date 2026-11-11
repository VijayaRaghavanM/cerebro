"""Records in a SQLite file, where the agent's tools can query them."""

import json
import sqlite3
from collections.abc import Callable, Iterable, Iterator
from contextlib import closing
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_origin
from urllib.parse import quote

from cerebro.adapters.sqlite import has_table, transaction
from cerebro.adapters.sqlite_comicvine import SqliteComicVineStore
from cerebro.domain.comicvine import ComicVineCharacter
from cerebro.domain.pages import Category
from cerebro.domain.records import (
    Character,
    Comic,
    Link,
    PageHit,
    Record,
    Story,
    Team,
)
from cerebro.ports.records import (
    RecordLookup,
    RecordReader,
    RecordsMissing,
    RecordStore,
)

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

SHARED_TABLES = [
    "CREATE TABLE IF NOT EXISTS links "
    "(kind TEXT, pageid INTEGER, story INTEGER, field TEXT, title TEXT, text TEXT)",
    "CREATE INDEX IF NOT EXISTS links_by_title ON links (title)",
    "CREATE INDEX IF NOT EXISTS links_by_record ON links (kind, pageid)",
    # Cast lists only, so counting a page's appearances never reads the link rows.
    "CREATE INDEX IF NOT EXISTS links_in_casts ON links (title, pageid)"
    f" WHERE kind = '{Category.COMICS}' AND field = 'appearing'",
    "CREATE TABLE IF NOT EXISTS categories (kind TEXT, pageid INTEGER, name TEXT)",
    "CREATE INDEX IF NOT EXISTS categories_by_name ON categories (name)",
    "CREATE INDEX IF NOT EXISTS categories_by_record ON categories (kind, pageid)",
]

# Fields stored in tables of their own rather than in a column.
ROW_FIELDS_LEFT_OUT = {"links", "categories", "stories"}

# The columns a search looks in, per table. A team has no current alias. Each table
# gets an index on them, so a search scans the names and never the long text fields.
# The display name is searched because some pages give their best-known name only
# there, such as "S.H.I.E.L.D." on the Earth-616 page.
NAME_COLUMNS = {
    Category.CHARACTERS: ["title", "name", "current_alias", "aliases", "display_name"],
    Category.TEAMS: ["title", "name", "aliases", "display_name"],
    # People write "Avengers #1 (1963)", and the title has no year.
    Category.COMICS: ["title", "year"],
}

# Searched and ranked apart, each up to the limit: appearances compare characters
# with teams but say nothing of comics, where the shortest title is the plainest match
# ("Avengers Vol 1 1" before "Avengers Annual Vol 1 1").
SEARCH_GROUPS = [
    ((Category.CHARACTERS, Category.TEAMS), "appearances DESC, title"),
    ((Category.COMICS,), "length(title), title"),
]

# Stripped from both ends of a search word: "#15" matches the "15" of "Vol 1 15",
# while an apostrophe inside a name ("Xi'an") stays.
EDGE_PUNCTUATION = "#.,;:!?\"'()"

# Builds a record from its row and the connection its links and categories are in.
type RowReader[R] = Callable[[sqlite3.Connection, sqlite3.Row], R]

WIKI_PAGES = "https://marvel.fandom.com/wiki/"
# Left readable in a citation; quote() encodes the rest.
URL_SAFE = "()',-:!&/"


class SqliteRecordStore(RecordStore, RecordReader, RecordLookup):
    """Records in one SQLite file.

    Each category has a table named after it, with a column per record field, and a
    comic's stories are in `stories`. Every record's links are in `links` and its
    categories in `categories`, keyed by category and page id, so they can be queried
    across kinds: which records link to X-Men (Earth-616)? Lists of names, such as a
    story's writers, are JSON arrays. The chunks of the character pages are in the
    same file but belong to `SqliteChunkIndex`; Comic Vine's tables belong to
    `SqliteComicVineStore`, which `comicvine()` reads through.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._comicvine = SqliteComicVineStore(path)

    # Writing: a whole category at a time.

    def replace(self, category: Category, records: Iterable[Record]) -> None:
        with transaction(self.path) as db:
            for statement in SHARED_TABLES:
                db.execute(statement)
            self._clear(db, category)
            created: set[str] = set()
            for record in records:
                self._insert(db, category, record, created)

            # The table only exists once a record has been written to it.
            if category in created:
                names = ", ".join(NAME_COLUMNS[category])
                db.execute(f'CREATE INDEX "{category}_names" ON "{category}" ({names})')

    # Reading: one record at a time, so a category is never held in memory whole.

    def characters(self) -> Iterator[Character]:
        return self._read(Category.CHARACTERS, _reader(Character, Category.CHARACTERS))

    def comics(self) -> Iterator[Comic]:
        return self._read(Category.COMICS, _comic)

    def _read[R](self, category: Category, read: RowReader[R]) -> Iterator[R]:
        # Checked before the generator starts, so a missing table fails at the call,
        # before a caller has opened anything to write the results to.
        if not has_table(self.path, category):
            raise RecordsMissing(f"No {category} are stored yet")

        return self._rows(category, read)

    def _rows[R](self, category: Category, read: RowReader[R]) -> Iterator[R]:
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute(f'SELECT * FROM "{category}" ORDER BY pageid'):
                yield read(db, row)

    # Lookup: by name, then by title.

    def find(self, name: str, limit: int) -> list[PageHit]:
        if not has_table(self.path, Category.CHARACTERS):
            raise RecordsMissing("No characters are stored yet")

        words = [word.strip(EDGE_PUNCTUATION) for word in name.split()]
        words = [word for word in words if word]
        if not words:
            return []

        hits: list[PageHit] = []
        with closing(sqlite3.connect(self.path)) as db:
            for categories, order in SEARCH_GROUPS:
                selects: list[str] = []
                params: list[Any] = []
                for category in categories:
                    if has_table(self.path, category):
                        condition, more = _all_words_in(NAME_COLUMNS[category], words)
                        selects.append(_hits_from(category, condition))
                        params.extend(more)
                if not selects:
                    continue

                sql = (
                    f"SELECT * FROM ({' UNION ALL '.join(selects)})"
                    f" ORDER BY {order} LIMIT ?"
                )
                found = db.execute(sql, [*params, limit]).fetchall()
                hits += [PageHit(title, Category(kind), n) for title, kind, n in found]

        return hits

    def record(self, title: str) -> Record | None:
        if not has_table(self.path, Category.CHARACTERS):
            raise RecordsMissing("No characters are stored yet")

        readers: list[tuple[Category, RowReader[Record]]] = [
            (Category.CHARACTERS, _reader(Character, Category.CHARACTERS)),
            (Category.TEAMS, _reader(Team, Category.TEAMS)),
            (Category.COMICS, _comic),
        ]
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for category, read in readers:
                if not has_table(self.path, category):
                    continue
                row = db.execute(
                    f'SELECT * FROM "{category}" WHERE title = ?', (title,)
                ).fetchone()
                if row is not None:
                    return read(db, row)
        return None

    def comicvine(self, pageid: int) -> ComicVineCharacter | None:
        return self._comicvine.character(pageid)

    def url(self, title: str) -> str:
        return WIKI_PAGES + quote(title.replace(" ", "_"), safe=URL_SAFE)

    # Writing, step by step.

    def _clear(self, db: sqlite3.Connection, category: Category) -> None:
        # Dropped, not emptied, so a table follows the record type when fields change.
        db.execute(f'DROP TABLE IF EXISTS "{category}"')
        if category is Category.COMICS:
            db.execute("DROP TABLE IF EXISTS stories")
        db.execute("DELETE FROM links WHERE kind = ?", (category,))
        db.execute("DELETE FROM categories WHERE kind = ?", (category,))

    def _insert(
        self,
        db: sqlite3.Connection,
        category: Category,
        record: Record,
        created: set[str],
    ) -> None:
        _insert_row(db, category, ("pageid",), _columns(record), created)
        db.executemany(
            "INSERT INTO categories VALUES (?, ?, ?)",
            [(category, record.pageid, name) for name in record.categories],
        )
        _insert_links(db, category, record.pageid, None, record.links)

        if isinstance(record, Comic):
            for story in record.stories:
                row = {"pageid": record.pageid, **_columns(story)}
                _insert_row(db, "stories", ("pageid", "number"), row, created)
                _insert_links(db, category, record.pageid, story.number, story.links)


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
    kind: Category,
    pageid: int,
    story: int | None,
    links: tuple[Link, ...],
) -> None:
    db.executemany(
        "INSERT INTO links VALUES (?, ?, ?, ?, ?, ?)",
        [(kind, pageid, story, link.field, link.title, link.text) for link in links],
    )


def _reader[R: DataclassInstance](cls: type[R], category: Category) -> RowReader[R]:
    """A reader for the records of one category that have no stories."""

    def read(db: sqlite3.Connection, row: sqlite3.Row) -> R:
        pageid = row["pageid"]
        return _from_columns(
            cls,
            row,
            categories=_categories_of(db, category, pageid),
            links=_links_of(db, category, pageid, story=None),
        )

    return read


def _comic(db: sqlite3.Connection, row: sqlite3.Row) -> Comic:
    pageid = row["pageid"]
    story_rows = db.execute(
        "SELECT * FROM stories WHERE pageid = ? ORDER BY number", (pageid,)
    )
    stories = tuple(
        _from_columns(
            Story,
            story,
            links=_links_of(db, Category.COMICS, pageid, story=story["number"]),
        )
        for story in story_rows
    )

    return _from_columns(
        Comic,
        row,
        stories=stories,
        categories=_categories_of(db, Category.COMICS, pageid),
        links=_links_of(db, Category.COMICS, pageid, story=None),
    )


def _categories_of(
    db: sqlite3.Connection, kind: Category, pageid: int
) -> tuple[str, ...]:
    rows = db.execute(
        "SELECT name FROM categories WHERE kind = ? AND pageid = ? ORDER BY rowid",
        (kind, pageid),
    )
    return tuple(name for (name,) in rows)


def _links_of(
    db: sqlite3.Connection, kind: Category, pageid: int, *, story: int | None
) -> tuple[Link, ...]:
    """A record's own links when `story` is None, else the links in that story."""
    # IS matches a None story to the NULL on a record's own links; = would match none.
    rows = db.execute(
        "SELECT field, title, text FROM links"
        " WHERE kind = ? AND pageid = ? AND story IS ? ORDER BY rowid",
        (kind, pageid, story),
    )
    return tuple(Link(field, title, text) for field, title, text in rows)


def _all_words_in(columns: list[str], words: list[str]) -> tuple[str, list[str]]:
    """A condition that holds when every word is in at least one of the columns."""
    clauses = []
    params = []
    for word in words:
        # Escaped, so a % or _ in the word matches itself.
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        likes = [f"{column} LIKE ? ESCAPE '\\'" for column in columns]
        clauses.append(f"({' OR '.join(likes)})")
        params.extend([f"%{escaped}%"] * len(columns))
    return " AND ".join(clauses), params


def _hits_from(category: Category, condition: str) -> str:
    """The SELECT for one table's hits: title, category and appearances."""
    if category is Category.COMICS:
        count = "0"
    else:
        # The page's title is what a cast list links to; a comic counts once however
        # many of its stories list the page. The `links_in_casts` index answers it.
        count = (
            "(SELECT COUNT(DISTINCT pageid) FROM links"
            f" WHERE kind = '{Category.COMICS}' AND field = 'appearing'"
            " AND title = page.title)"
        )
    return (
        f"SELECT title, '{category}' AS category, {count} AS appearances"
        f' FROM "{category}" AS page WHERE {condition}'
    )
