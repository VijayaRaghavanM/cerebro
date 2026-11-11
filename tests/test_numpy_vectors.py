import json
from pathlib import Path

import numpy as np
import pytest

from cerebro.adapters.numpy_vectors import NumpyVectorStore


def test_a_saved_part_reads_back_as_float32_rows_and_ids(tmp_path: Path) -> None:
    store = NumpyVectorStore(tmp_path / "text")
    assert not store.has_part(3)

    store.save_part(3, ["1:7:0", "1:7:1"], [[0.5, 1.0], [2.0, 4.0]])

    assert store.has_part(3)
    vectors = np.load(tmp_path / "text" / "part-00003.npy")
    assert vectors.dtype == np.float32
    assert vectors.tolist() == [[0.5, 1.0], [2.0, 4.0]]
    ids = json.loads((tmp_path / "text" / "part-00003.json").read_text("utf-8"))
    assert ids == ["1:7:0", "1:7:1"]


def test_a_part_is_not_there_until_its_ids_are(tmp_path: Path) -> None:
    store = NumpyVectorStore(tmp_path)
    np.save(tmp_path / "part-00000.npy", np.zeros((1, 2), dtype=np.float32))

    assert not store.has_part(0)

    (tmp_path / "part-00000.json").write_text('["1:7:0"]', encoding="utf-8")

    assert store.has_part(0)


def test_a_run_stopped_while_saving_leaves_no_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_replace = Path.replace

    def stop_at_the_vectors(self: Path, target: Path) -> Path:
        if Path(target).suffix == ".npy":
            raise KeyboardInterrupt
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", stop_at_the_vectors)
    store = NumpyVectorStore(tmp_path)

    with pytest.raises(KeyboardInterrupt):
        store.save_part(0, ["1:7:0"], [[1.0]])

    assert not store.has_part(0)
