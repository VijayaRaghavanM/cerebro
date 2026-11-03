from pathlib import Path

import pytest

from cerebro.settings import Settings

ENV_EXAMPLE = Path(__file__).parents[1] / ".env.example"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test in an empty folder with no real keys from the shell."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_reads_key_from_dotenv_in_working_directory(isolated: Path) -> None:
    (isolated / ".env").write_text("MISTRAL_API_KEY=from-file\n")
    key = Settings().mistral_api_key
    assert key is not None
    assert key.get_secret_value() == "from-file"


def test_loads_without_any_keys() -> None:
    assert Settings().mistral_api_key is None


def test_key_never_appears_when_settings_are_printed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "not-a-real-key")
    settings = Settings()
    assert "not-a-real-key" not in repr(settings)
    assert "not-a-real-key" not in str(settings)


def test_env_example_documents_every_setting() -> None:
    lines = ENV_EXAMPLE.read_text().splitlines()
    documented = {
        line.split("=", 1)[0].strip()
        for line in lines
        if "=" in line and not line.lstrip().startswith("#")
    }
    fields = {name.upper() for name in Settings.model_fields}
    assert fields <= documented, f"missing from .env.example: {fields - documented}"
