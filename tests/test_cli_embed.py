from pathlib import Path

import pytest
from typer.testing import CliRunner

from cerebro.interfaces.cli import app


def test_embedding_without_a_server_setting_says_what_to_set(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    result = CliRunner().invoke(app, ["embed"])

    assert result.exit_code == 1
    assert "Set OLLAMA_BASE_URL to embed chunks." in result.output


def test_embedding_before_chunking_says_what_to_run(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Nothing is sent: the missing chunks are found first.
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")

    result = CliRunner().invoke(app, ["embed"])

    assert result.exit_code == 1
    assert "No chunks are stored yet. Run `cerebro chunk` first." in result.output
    assert not (data_dir / "embeddings").exists()
