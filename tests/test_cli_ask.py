from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cerebro import bootstrap
from cerebro.domain.answers import Answer, Source, Step, ToolCall, ToolReply
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


# The real bootstrap.ask calls Mistral, so the tests replace it at this seam. The
# steps are yielded one by one, and an exception is raised where it would arrive.
def fake_ask(monkeypatch: pytest.MonkeyPatch, *steps: Step | Exception) -> None:
    def ask(
        question: str, model: bootstrap.Contestant = bootstrap.Contestant.MINISTRAL_14B
    ) -> Iterator[Step]:
        for step in steps:
            if isinstance(step, Exception):
                raise step
            yield step

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
        "\n"
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
        "\n"
        "Wolverine's real name is James Howlett [1].\n"
        "\n"
        "No sources cited.\n"
        "\n"
        "5 model calls, 4 tool calls, 8,636 tokens in, 102 out, 151 s\n"
    )


def test_ask_prints_each_step_before_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ask(
        monkeypatch,
        ToolCall("search_pages", "Wolverine"),
        ToolReply("search_pages", "James Howlett (Earth-616)\nmore\nlines"),
        ToolCall("read_page", "James Howlett (Earth-616)"),
        ToolReply("read_page", "Page: James Howlett (Earth-616)\nReal name: James"),
        answer(),
    )

    result = CliRunner().invoke(app, ["ask", "Who is Wolverine?"])

    assert result.exit_code == 0
    assert result.output == (
        "search_pages: Wolverine\n"
        "  James Howlett (Earth-616)\n"
        "read_page: James Howlett (Earth-616)\n"
        "  Page: James Howlett (Earth-616)\n"
        "\n"
        "Wolverine's real name is James Howlett [1].\n"
        "\n"
        "No sources cited.\n"
        "\n"
        "5 model calls, 4 tool calls, 8,636 tokens in, 102 out, 151 s\n"
    )


def test_ask_shows_only_the_first_line_of_a_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ask(
        monkeypatch,
        ToolCall("read_page", "Thor"),
        ToolReply("read_page", "Page: Thor\n" + "Long body text. " * 500),
        answer(),
    )

    result = CliRunner().invoke(app, ["ask", "Who is Thor?"])

    assert "  Page: Thor\n" in result.output
    assert "Long body text" not in result.output


def test_ask_reports_a_failure_that_comes_after_some_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ask(
        monkeypatch,
        ToolCall("search_pages", "Wolverine"),
        ToolReply("search_pages", "James Howlett (Earth-616)"),
        RateLimited(),
    )

    result = CliRunner().invoke(app, ["ask", "Who is Wolverine?"])

    assert result.exit_code == 1
    assert result.output == (
        "search_pages: Wolverine\n"
        "  James Howlett (Earth-616)\n"
        "Mistral is rate limiting requests; try again in a minute.\n"
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
