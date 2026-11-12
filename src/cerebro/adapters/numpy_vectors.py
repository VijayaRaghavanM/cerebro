"""Vectors in numbered NumPy files, one part per pair of files."""

import json
from pathlib import Path

import numpy as np

from cerebro.ports.embeddings import VectorIndex, VectorsMissing, VectorStore


class NumpyVectorStore(VectorStore):
    """Part n is `part-<n>.npy` (a float32 row per chunk) and `part-<n>.json` (the
    chunk ids, in row order).
    """

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def has_part(self, number: int) -> bool:
        return self._ids_path(number).exists()

    def save_part(
        self, number: int, chunk_ids: list[str], vectors: list[list[float]]
    ) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        vectors_path = self._vectors_path(number)
        ids_path = self._ids_path(number)
        vectors_temp = vectors_path.with_name(vectors_path.name + ".tmp")
        ids_temp = ids_path.with_name(ids_path.name + ".tmp")

        with vectors_temp.open("wb") as file:
            np.save(file, np.asarray(vectors, dtype=np.float32))
        ids_temp.write_text(json.dumps(chunk_ids), encoding="utf-8")

        # Renamed into place with the ids last, because `has_part` looks at the ids:
        # a stopped run must not leave a half part that a rerun would skip.
        vectors_temp.replace(vectors_path)
        ids_temp.replace(ids_path)

    def _vectors_path(self, number: int) -> Path:
        return self.folder / f"part-{number:05d}.npy"

    def _ids_path(self, number: int) -> Path:
        return self.folder / f"part-{number:05d}.json"


class NumpyVectorIndex(VectorIndex):
    """The parts `NumpyVectorStore` saved, read as one matrix on the first search.

    It sits beside the store because both own the file layout. The whole matrix
    stays in memory, about a gigabyte for the stored chunks, and is read once per
    index.
    """

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._ids: list[str] | None = None
        self._matrix: np.ndarray | None = None

    def nearest(self, vector: list[float], limit: int) -> list[tuple[str, float]]:
        if self._ids is None or self._matrix is None:
            self._ids, self._matrix = self._load()

        # The vectors have length 1, so the dot product is the cosine.
        scores = self._matrix @ np.asarray(vector, dtype=np.float32)

        # A partition finds the best `count` without sorting 300,000 scores; only
        # those few are then sorted, ties by row so that a repeat gives the same order.
        count = min(limit, len(scores))
        best = np.argpartition(scores, -count)[-count:]
        ordered = best[np.lexsort((best, -scores[best]))]

        return [(self._ids[row], float(scores[row])) for row in ordered]

    def _load(self) -> tuple[list[str], np.ndarray]:
        id_files = sorted(self.folder.glob("part-*.json"))
        if not id_files:
            raise VectorsMissing("No vectors are stored yet")

        ids: list[str] = []
        for path in id_files:
            ids.extend(json.loads(path.read_text(encoding="utf-8")))

        # Each part is mapped, not read, so the parts are copied straight into one
        # matrix and never held twice; joining them afterwards would need double.
        parts = [np.load(path.with_suffix(".npy"), mmap_mode="r") for path in id_files]
        matrix = np.empty((len(ids), parts[0].shape[1]), dtype=np.float32)
        start = 0
        for part in parts:
            matrix[start : start + len(part)] = part
            start += len(part)

        return ids, matrix
