import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from cerebro.adapters.numpy_vectors import NumpyVectorStore
from cerebro.application import embedding
from cerebro.application.embedding import EmbedReport, embed_chunks
from cerebro.domain.chunks import Chunk
from cerebro.ports.chunks import ChunkReader
from cerebro.ports.embeddings import Embedder, EmbedderUnavailable


class FakeChunks(ChunkReader):
    def __init__(self, count: int) -> None:
        # Chunk n's text is n + 1 letters, so a vector shows whose text it came from.
        self.stored = [
            Chunk(f"1:7:{n}", 1, 7, n, "Ann Doe", "History", "p", "a" * (n + 1))
            for n in range(count)
        ]

    def chunks(self) -> Iterator[Chunk]:
        return iter(self.stored)


class FakeEmbedder(Embedder):
    """Embeds a text as its length, and keeps the size of each request."""

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.batch_sizes: list[int] = []
        self.fail_on_call = fail_on_call

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        if len(self.batch_sizes) == self.fail_on_call:
            raise EmbedderUnavailable("down")
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def small_sizes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parts of 4 chunks and batches of 3, so a few chunks cover every case."""
    monkeypatch.setattr(embedding, "PART_SIZE", 4)
    monkeypatch.setattr(embedding, "BATCH_SIZE", 3)


def test_chunks_are_saved_in_parts_with_their_ids_in_row_order(tmp_path: Path) -> None:
    store = NumpyVectorStore(tmp_path)

    report = embed_chunks(FakeChunks(10), FakeEmbedder(), store)

    assert report == EmbedReport(chunks=10, parts=3, skipped_parts=0)
    for number, expected in enumerate([range(0, 4), range(4, 8), range(8, 10)]):
        ids = json.loads((tmp_path / f"part-{number:05d}.json").read_text("utf-8"))
        vectors = np.load(tmp_path / f"part-{number:05d}.npy")
        assert ids == [f"1:7:{n}" for n in expected]
        assert vectors.shape == (len(expected), 1)
        assert vectors[:, 0].tolist() == [n + 1 for n in expected]


def test_texts_are_embedded_in_batches(tmp_path: Path) -> None:
    embedder = FakeEmbedder()

    embed_chunks(FakeChunks(10), embedder, NumpyVectorStore(tmp_path))

    # Parts of 4, and 3 per request within a part; a batch never spans two parts.
    assert embedder.batch_sizes == [3, 1, 3, 1, 2]


def test_a_rerun_skips_finished_parts_and_embeds_nothing(tmp_path: Path) -> None:
    store = NumpyVectorStore(tmp_path)
    embed_chunks(FakeChunks(10), FakeEmbedder(), store)
    embedder = FakeEmbedder()

    report = embed_chunks(FakeChunks(10), embedder, store)

    assert report == EmbedReport(chunks=10, parts=3, skipped_parts=3)
    assert embedder.batch_sizes == []


def test_a_failure_mid_part_keeps_earlier_parts_and_leaves_no_half_part(
    tmp_path: Path,
) -> None:
    store = NumpyVectorStore(tmp_path)
    # The fourth request is the second batch of the second part.
    failing = FakeEmbedder(fail_on_call=4)

    with pytest.raises(EmbedderUnavailable):
        embed_chunks(FakeChunks(10), failing, store)

    assert store.has_part(0)
    assert not store.has_part(1)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "part-00000.json",
        "part-00000.npy",
    ]

    report = embed_chunks(FakeChunks(10), FakeEmbedder(), store)
    assert report == EmbedReport(chunks=10, parts=3, skipped_parts=1)


def test_progress_counts_chunks_done_out_of_the_total(tmp_path: Path) -> None:
    store = NumpyVectorStore(tmp_path)
    embed_chunks(FakeChunks(4), FakeEmbedder(), store)
    seen: list[tuple[int, int]] = []

    embed_chunks(
        FakeChunks(10),
        FakeEmbedder(),
        store,
        progress=lambda done, total: seen.append((done, total)),
    )

    # The finished part counts as done at once; the rest advance by batch.
    assert seen == [(4, 10), (7, 10), (8, 10), (10, 10)]
