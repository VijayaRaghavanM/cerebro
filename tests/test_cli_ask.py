from pathlib import Path

import pytest
from typer.testing import CliRunner

from cerebro import bootstrap
from cerebro.domain.answers import Answer, Source
from cerebro.interfaces.cli import app
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.records import RecordsMissing


def answer(*sources: Source) -> Answer:
    return Answer(
        text="Wolverine's real name is James Howlett [1].",
        sources=sources,
        model_calls=5,
        tool_calls=4,
        input_tokens=8636,
        output_tokens=102,
        seconds=150.6,
    )


# The real bootstrap.ask calls Mistral, so the tests replace it at this seam.
def fake_ask(monkeypatch: pytest.MonkeyPatch, result: Answer | Exception) -> None:
    def ask(question: str) -> Answer:
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(bootstrap, "ask", ask)


def test_ask_without_a_key_says_which_variable_to_set(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    result = CliRunner().invoke(app, ["ask", "Who is Wolverine?"])

    assert result.exit_code == 1
    assert result.output == "Set MISTRAL_API_KEY to ask questions.\n"


def test_ask_prints_the_answer_its_sources_and_what_it_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://marvel.fandom.com/wiki/James_Howlett_(Earth-616)"
    fake_ask(monkeypatch, answer(Source("James Howlett (Earth-616)", url)))

    result = CliRunner().invoke(app, ["ask", "What is Wolverine's real name?"])

    assert result.exit_code == 0
    assert result.output == (
        "Wolverine's real name is James Howlett [1].\n"
        "\n"
        f"[1] James Howlett (Earth-616): {url}\n"
        "\n"
        "5 model calls, 4 tool calls, 8,636 tokens in, 102 out, 151 s\n"
    )


def test_ask_numbers_every_source(monkeypatch: pytest.MonkeyPatch) -> None:
    sources = (
        Source("James Howlett (Earth-616)", "https://example.test/a"),
        Source("Uncanny X-Men Vol 1 1", "https://example.test/b"),
    )
    fake_ask(monkeypatch, answer(*sources))

    result = CliRunner().invoke(app, ["ask", "Who is Wolverine?"])

    assert "[1] James Howlett (Earth-616): https://example.test/a\n" in result.output
    assert "[2] Uncanny X-Men Vol 1 1: https://example.test/b\n" in result.output


def test_ask_says_when_no_sources_are_cited(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ask(monkeypatch, answer())

    result = CliRunner().invoke(app, ["ask", "Who is Wolverine?"])

    assert result.exit_code == 0
    assert result.output == (
        "Wolverine's real name is James Howlett [1].\n"
        "\n"
        "No sources cited.\n"
        "\n"
        "5 model calls, 4 tool calls, 8,636 tokens in, 102 out, 151 s\n"
    )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            RecordsMissing("No characters are stored yet"),
            "No characters are stored yet. Run `cerebro parse fandom` first.",
        ),
        (
            RateLimited(),
            "Mistral is rate limiting requests; try again in a minute.",
        ),
        (ModelTimeout(), "Mistral did not reply in time."),
        (ProviderError("Mistral said no"), "Mistral said no"),
    ],
)
def test_ask_reports_a_failure_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    fake_ask(monkeypatch, error)

    result = CliRunner().invoke(app, ["ask", "Who is Wolverine?"])

    assert result.exit_code == 1
    assert result.output == f"{message}\n"
