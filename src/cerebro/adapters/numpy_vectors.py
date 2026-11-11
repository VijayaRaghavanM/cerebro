"""Vectors in numbered NumPy files, one part per pair of files."""

import json
from pathlib import Path

import numpy as np

from cerebro.ports.embeddings import VectorStore


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
