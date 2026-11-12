"""Chunks and their search index in a SQLite file."""

import re
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing
from dataclasses import astuple
from pathlib import Path

from cerebro.adapters.sqlite import has_table, transaction
from cerebro.domain.chunks import Chunk, ChunkHit
from cerebro.ports.chunks import ChunkLookup, ChunkReader, ChunkSearch, ChunkStore
from cerebro.ports.records import RecordsMissing

# What a chunk search reads from a query: runs of letters and digits, as the index's
# tokenizer splits text. Keeping "Wolverine's" whole would make it the two-word
# phrase "wolverine s", which almost never occurs.
SEARCH_WORD = re.compile(r"\w+")


class SqliteChunkIndex(ChunkStore, ChunkSearch, ChunkReader, ChunkLookup):
    """Character page chunks and their BM25 index, in the records file.

    The index holds each chunk's prefix and its text as two columns, so the prefix
    arms can be compared on one index; `search` reads the text.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    # Writing: all the chunks at once.

    def replace_chunks(self, chunks: Iterable[Chunk]) -> None:
        with transaction(self.path) as db:
            db.execute("DROP TABLE IF EXISTS chunks")
            db.execute(
                "CREATE TABLE chunks (id TEXT PRIMARY KEY, pageid INTEGER,"
                " revid INTEGER, number INTEGER, title TEXT, section TEXT,"
                " prefix TEXT, text TEXT)"
            )
            db.execute("CREATE INDEX chunks_by_page ON chunks (pageid)")
            # The columns follow `Chunk`'s field order.
            db.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (astuple(chunk) for chunk in chunks),
            )

            # Porter stems inflections ("powers" finds "power"); unicode61 folds
            # diacritics, so "Xuan" finds "Xuân". The prefix and text are read from
            # `chunks`, not stored a second time.
            db.execute("DROP TABLE IF EXISTS chunks_fts")
            db.execute(
                "CREATE VIRTUAL TABLE chunks_fts USING fts5(prefix, text,"
                " content='chunks', content_rowid='rowid',"
                " tokenize='porter unicode61 remove_diacritics 2')"
            )
            db.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")

    # Reading: all the chunks in the order they were stored, or some by id.

    def chunks(self) -> Iterator[Chunk]:
        # Checked before the generator starts, so a missing table fails at the call.
        if not has_table(self.path, "chunks"):
            raise RecordsMissing("No chunks are stored yet")

        return self._rows()

    def _rows(self) -> Iterator[Chunk]:
        with closing(sqlite3.connect(self.path)) as db:
            for row in db.execute("SELECT * FROM chunks ORDER BY rowid"):
                yield Chunk(*row)

    def chunks_by_id(self, ids: list[str]) -> list[Chunk]:
        if not has_table(self.path, "chunks"):
            raise RecordsMissing("No chunks are stored yet")

        if not ids:
            return []

        marks = ", ".join("?" * len(ids))
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(f"SELECT * FROM chunks WHERE id IN ({marks})", ids)
            found = {row[0]: Chunk(*row) for row in rows}

        return [found[id] for id in ids if id in found]

    # Searching.

    def search(self, query: str, limit: int) -> list[ChunkHit]:
        if not has_table(self.path, "chunks"):
            raise RecordsMissing("No chunks are stored yet")

        words = SEARCH_WORD.findall(query)
        if not words:
            return []

        # OR, because a natural question rarely has every word in one chunk; bm25
        # weighs the rare words most. Each term is quoted so that a word like "AND" or
        # "NEAR" is read as text; a word never holds a quote, so none needs escaping.
        terms = [f'"{word}"' for word in words]
        # The text column only: matching the prefix too ranked worse on the
        # measured questions (a name in the query then matches every chunk of every
        # same-named page). The prefix stays indexed for the other prefix arms.
        match = f"text : ({' OR '.join(terms)})"
        with closing(sqlite3.connect(self.path)) as db:
            # bm25 is lower for a better match, so the score is its negation. The top
            # rows are picked before the join, so it no longer reads every matching
            # chunk; the outer ORDER BY keeps them best first.
            found = db.execute(
                "SELECT c.*, top.score FROM ("
                "SELECT rowid, -bm25(chunks_fts) AS score FROM chunks_fts"
                " WHERE chunks_fts MATCH ? ORDER BY score DESC, rowid LIMIT ?"
                ") AS top JOIN chunks c ON c.rowid = top.rowid"
                " ORDER BY top.score DESC, top.rowid",
                (match, limit),
            ).fetchall()

        return [ChunkHit(Chunk(*row[:-1]), row[-1]) for row in found]
