from collections.abc import Iterator

import pytest
from langchain_openai import ChatOpenAI
from typer.testing import CliRunner

from cerebro import bootstrap
from cerebro.bootstrap import Contestant, MissingKey, chat_model
from cerebro.domain.answers import Step
from cerebro.interfaces.cli import app

OPENROUTER_URL = "https://openrouter.ai/api/v1"
PIN_TO_MISTRAL = {"provider": {"order": ["Mistral"], "allow_fallbacks": False}}


@pytest.fixture(autouse=True)
def keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real settings, with test keys and an Ollama server set."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")


def built(contestant: Contestant) -> ChatOpenAI:
    model = chat_model(contestant)
    assert isinstance(model, ChatOpenAI)
    return model


@pytest.mark.parametrize(
    ("contestant", "model_id"),
    [
        (Contestant.MINISTRAL_14B_OPENROUTER, "mistralai/ministral-14b-2512"),
        (Contestant.MINISTRAL_3B_OPENROUTER, "mistralai/ministral-3b-2512"),
    ],
)
def test_a_ministral_on_openrouter_is_served_only_by_mistral(
    contestant: Contestant, model_id: str
) -> None:
    model = built(contestant)

    assert model.openai_api_base == OPENROUTER_URL
    assert model.model_name == model_id
    assert model.extra_body == PIN_TO_MISTRAL
    assert model.temperature == 0


def test_gemini_on_openrouter_is_not_pinned_to_a_provider() -> None:
    model = built(Contestant.GEMINI_FLASH_OPENROUTER)

    assert model.openai_api_base == OPENROUTER_URL
    assert model.model_name == "google/gemini-3.8-flash"
    assert model.extra_body is None


def test_qwen_runs_on_the_ollama_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434/")

    model = built(Contestant.QWEN3_14B_OLLAMA)

    assert model.openai_api_base == "http://ollama.test:11434/v1"
    assert model.model_name == "qwen3:14b"


@pytest.mark.parametrize(
    ("contestant", "variable"),
    [
        (Contestant.MINISTRAL_14B, "MISTRAL_API_KEY"),
        (Contestant.MINISTRAL_14B_OPENROUTER, "OPENROUTER_API_KEY"),
        (Contestant.MINISTRAL_3B_OPENROUTER, "OPENROUTER_API_KEY"),
        (Contestant.GEMINI_FLASH_OPENROUTER, "OPENROUTER_API_KEY"),
        (Contestant.QWEN3_14B_OLLAMA, "OLLAMA_BASE_URL"),
    ],
)
def test_a_missing_key_names_its_variable(
    monkeypatch: pytest.MonkeyPatch, contestant: Contestant, variable: str
) -> None:
    monkeypatch.delenv(variable)

    with pytest.raises(MissingKey, match=variable):
        chat_model(contestant)


def test_ask_passes_the_chosen_model_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen: list[Contestant] = []

    def ask(question: str, model: Contestant) -> Iterator[Step]:
        chosen.append(model)
        return iter(())

    monkeypatch.setattr(bootstrap, "ask", ask)

    CliRunner().invoke(app, ["ask", "--model", "qwen3-14b-ollama", "Who is Thor?"])

    assert chosen == [Contestant.QWEN3_14B_OLLAMA]


def test_ask_uses_the_free_mistral_model_unless_told_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen: list[Contestant] = []

    def ask(question: str, model: Contestant) -> Iterator[Step]:
        chosen.append(model)
        return iter(())

    monkeypatch.setattr(bootstrap, "ask", ask)

    CliRunner().invoke(app, ["ask", "Who is Thor?"])

    assert chosen == [Contestant.MINISTRAL_14B]
