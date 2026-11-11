"""Records in a SQLite file, where the agent's tools can query them."""

import json
import sqlite3
from collections.abc import Callable, Iterable, Iterator
from contextlib import closing
from dataclasses import Field, asdict, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_args, get_origin
from urllib.parse import quote

from cerebro.domain.comicvine import (
    CharacterMatch,
    ComicVineCharacter,
    ComicVineDetail,
    ComicVineIssue,
)
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
from cerebro.ports.comicvine import ComicVineStore, MatchStore
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
    " WHERE kind = 'comics' AND field = 'appearing'",
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

# The columns a search looks in, per table. A team has no current alias. Each table
# gets an index on them, so a search scans the names and never the long text fields.
NAME_COLUMNS = {
    Category.CHARACTERS: ["title", "name", "current_alias", "aliases"],
    Category.TEAMS: ["title", "name", "aliases"],
    Category.COMICS: ["title"],
}

# Stripped from both ends of a search word: "#15" matches the "15" of "Vol 1 15",
# while an apostrophe inside a name ("Xi'an") stays.
EDGE_PUNCTUATION = "#.,;:!?\"'()"

# Builds a record from its row and the connection its links and categories are in.
type RowReader = Callable[[sqlite3.Connection, sqlite3.Row], Record]

WIKI_PAGES = "https://marvel.fandom.com/wiki/"
# Left readable in a citation; quote() encodes the rest.
URL_SAFE = "()',-:!&/"


class SqliteRecordStore(
    RecordStore, RecordReader, RecordLookup, MatchStore, ComicVineStore
):
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

                # The table only exists once a record has been written to it.
                if str(category) in created:
                    names = ", ".join(NAME_COLUMNS[category])
                    db.execute(
                        f'CREATE INDEX "{category}_names" ON "{category}" ({names})'
                    )

    # Reading: one record at a time, so a category is never held in memory whole.

    def characters(self) -> Iterator[Character]:
        if not self._stored("characters"):
            raise RecordsMissing("No characters are stored yet")

        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute("SELECT * FROM characters ORDER BY pageid"):
                yield _character(db, row)

    def comics(self) -> Iterator[Comic]:
        if not self._stored("comics"):
            raise RecordsMissing("No comics are stored yet")

        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute("SELECT * FROM comics ORDER BY pageid"):
                yield _comic(db, row)

    # Lookup: by name, then by title.

    def find(self, name: str, limit: int) -> list[PageHit]:
        if not self._stored("characters"):
            raise RecordsMissing("No characters are stored yet")

        words = [word.strip(EDGE_PUNCTUATION) for word in name.split()]
        words = [word for word in words if word]
        if not words:
            return []

        selects: list[str] = []
        params: list[Any] = []
        for category, columns in NAME_COLUMNS.items():
            if self._stored(category):
                condition, condition_params = _all_words_in(columns, words)
                selects.append(_hits_from(category, condition))
                params.extend(condition_params)

        # Comics have no appearances, so they sort after any character that has some;
        # the second key keeps them behind characters and teams that have none.
        sql = (
            f"SELECT * FROM ({' UNION ALL '.join(selects)})"
            " ORDER BY appearances DESC, category = 'comics', title LIMIT ?"
        )
        with closing(sqlite3.connect(self.path)) as db:
            found = db.execute(sql, [*params, limit]).fetchall()
        return [PageHit(title, Category(kind), count) for title, kind, count in found]

    def record(self, title: str) -> Record | None:
        if not self._stored("characters"):
            raise RecordsMissing("No characters are stored yet")

        readers: list[tuple[Category, RowReader]] = [
            (Category.CHARACTERS, _character),
            (Category.TEAMS, _team),
            (Category.COMICS, _comic),
        ]
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            for category, read in readers:
                if not self._stored(category):
                    continue
                row = db.execute(
                    f'SELECT * FROM "{category}" WHERE title = ?', (title,)
                ).fetchone()
                if row is not None:
                    return read(db, row)
        return None

    def comicvine(self, pageid: int) -> ComicVineCharacter | None:
        # Either table is missing until `cerebro load comicvine` and the match have run.
        if not (
            self._stored("comicvine_matches") and self._stored("comicvine_characters")
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

    def url(self, title: str) -> str:
        return WIKI_PAGES + quote(title.replace(" ", "_"), safe=URL_SAFE)

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


def _character(db: sqlite3.Connection, row: sqlite3.Row) -> Character:
    pageid = row["pageid"]
    return _from_columns(
        Character,
        row,
        categories=_categories_of(db, "characters", pageid),
        links=_links_of(db, "characters", pageid, story=None),
    )


def _team(db: sqlite3.Connection, row: sqlite3.Row) -> Team:
    pageid = row["pageid"]
    return _from_columns(
        Team,
        row,
        categories=_categories_of(db, "teams", pageid),
        links=_links_of(db, "teams", pageid, story=None),
    )


def _comic(db: sqlite3.Connection, row: sqlite3.Row) -> Comic:
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

    return _from_columns(
        Comic,
        row,
        stories=stories,
        categories=_categories_of(db, "comics", pageid),
        links=_links_of(db, "comics", pageid, story=None),
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
            " WHERE kind = 'comics' AND field = 'appearing' AND title = page.title)"
        )
    return (
        f"SELECT title, '{category}' AS category, {count} AS appearances"
        f' FROM "{category}" AS page WHERE {condition}'
    )
