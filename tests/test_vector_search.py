"""Search by meaning: the stored vectors, and the chunks nearest a query."""

from pathlib import Path

import pytest

from cerebro.adapters.numpy_vectors import NumpyVectorIndex, NumpyVectorStore
from cerebro.adapters.sqlite_chunks import SqliteChunkIndex
from cerebro.adapters.vector_chunks import VectorChunkSearch
from cerebro.domain.chunks import Chunk
from cerebro.ports.embeddings import Embedder, VectorsMissing


def stored_vectors(folder: Path) -> NumpyVectorIndex:
    """Four unit vectors in two parts."""
    store = NumpyVectorStore(folder)
    store.save_part(0, ["a", "b"], [[1.0, 0.0], [0.0, 1.0]])
    store.save_part(1, ["c", "d"], [[0.6, 0.8], [-1.0, 0.0]])
    return NumpyVectorIndex(folder)


def test_the_nearest_vectors_are_found_across_parts_best_first(
    tmp_path: Path,
) -> None:
    index = stored_vectors(tmp_path)

    found = index.nearest([0.8, 0.6], limit=3)

    # Dot products: c 0.96 (part 1), a 0.8 (part 0), b 0.6 (part 0).
    assert [chunk_id for chunk_id, _ in found] == ["c", "a", "b"]
    assert [score for _, score in found] == pytest.approx([0.96, 0.8, 0.6])


def test_asking_for_more_than_is_stored_gives_all_of_it(tmp_path: Path) -> None:
    index = stored_vectors(tmp_path)

    found = index.nearest([0.8, 0.6], limit=10)

    assert [chunk_id for chunk_id, _ in found] == ["c", "a", "b", "d"]


def test_equal_scores_come_back_in_stored_order(tmp_path: Path) -> None:
    store = NumpyVectorStore(tmp_path)
    store.save_part(0, ["x", "y", "z"], [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])

    found = NumpyVectorIndex(tmp_path).nearest([1.0, 0.0], limit=3)

    assert [chunk_id for chunk_id, _ in found] == ["x", "y", "z"]


def test_the_vectors_are_read_on_the_first_search_and_once(tmp_path: Path) -> None:
    folder = tmp_path / "text"
    index = NumpyVectorIndex(folder)
    stored_vectors(folder)

    first = index.nearest([1.0, 0.0], limit=2)
    for file in folder.iterdir():
        file.unlink()
    second = index.nearest([1.0, 0.0], limit=2)

    assert first == second


def test_searching_with_no_vectors_stored_says_so(tmp_path: Path) -> None:
    with pytest.raises(VectorsMissing):
        NumpyVectorIndex(tmp_path / "text").nearest([1.0, 0.0], limit=1)


class FakeEmbedder(Embedder):
    """Embeds every query as the vector given, and keeps the queries."""

    def __init__(self, query_vector: list[float]) -> None:
        self.query_vector = query_vector
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("a search embeds no documents")

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return self.query_vector


def chunk(chunk_id: str, text: str) -> Chunk:
    number = int(chunk_id.rsplit(":", 1)[1])
    return Chunk(chunk_id, 1, 7, number, "Ann Doe (Earth-1)", "History", "", text)


def test_a_search_returns_the_chunks_nearest_the_query_best_first(
    tmp_path: Path,
) -> None:
    chunks = SqliteChunkIndex(tmp_path / "records.sqlite")
    chunks.replace_chunks(
        [chunk("1:7:0", "zero"), chunk("1:7:1", "one"), chunk("1:7:2", "two")]
    )
    store = NumpyVectorStore(tmp_path / "text")
    store.save_part(0, ["1:7:0", "1:7:1"], [[1.0, 0.0], [0.0, 1.0]])
    store.save_part(1, ["1:7:2"], [[0.6, 0.8]])
    embedder = FakeEmbedder([0.0, 1.0])
    search = VectorChunkSearch(embedder, NumpyVectorIndex(tmp_path / "text"), chunks)

    hits = search.search("who rules the clouds", limit=2)

    assert embedder.queries == ["who rules the clouds"]
    assert [hit.chunk.text for hit in hits] == ["one", "two"]
    assert [hit.score for hit in hits] == pytest.approx([1.0, 0.8])


def test_a_vector_whose_chunk_is_gone_is_left_out(tmp_path: Path) -> None:
    chunks = SqliteChunkIndex(tmp_path / "records.sqlite")
    chunks.replace_chunks([chunk("1:7:0", "zero")])
    store = NumpyVectorStore(tmp_path / "text")
    store.save_part(0, ["9:9:9", "1:7:0"], [[1.0, 0.0], [0.6, 0.8]])
    search = VectorChunkSearch(
        FakeEmbedder([1.0, 0.0]), NumpyVectorIndex(tmp_path / "text"), chunks
    )

    hits = search.search("anything", limit=2)

    assert [hit.chunk.id for hit in hits] == ["1:7:0"]
