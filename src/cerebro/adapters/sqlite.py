"""What the SQLite adapters share: opening a write, and asking what a file holds."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    """One write: it commits when the block ends, and rolls back if it raises."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # A write can stream from a reader open on this same file, as the chunk step
    # does; without WAL it would wait on that reader forever. The mode is kept in
    # the file and can only change outside a transaction, hence the autocommit
    # connection.
    with closing(sqlite3.connect(path, autocommit=True)) as db:
        db.execute("PRAGMA journal_mode = WAL")

    # autocommit=False keeps every statement in the transaction, the DROP TABLE
    # included; by default sqlite3 runs that outside one.
    with closing(sqlite3.connect(path, autocommit=False)) as db:
        with db:
            yield db


def has_table(path: Path, name: str) -> bool:
    # Checked before connecting, which would create an empty file.
    if not path.exists():
        return False

    with closing(sqlite3.connect(path)) as db:
        found = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        )
        return found.fetchone() is not None
