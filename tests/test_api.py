import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cerebro import bootstrap
from cerebro.domain.answers import Answer, Source, Step, ToolCall, ToolReply
from cerebro.interfaces.api import app
from cerebro.ports.agent import RateLimited

client = TestClient(app)


def answer() -> Answer:
    return Answer(
        text="Wolverine's real name is James Howlett [1].",
        sources=(Source("James Howlett (Earth-616)", "https://example.test/a"),),
        model_calls=5,
        tool_calls=4,
        input_tokens=8636,
        output_tokens=102,
        seconds=150.6,
    )


# The real bootstrap.ask calls Mistral, so the tests replace it at this seam. The
# steps are yielded one by one, and an exception is raised where it would arrive.
def fake_ask(monkeypatch: pytest.MonkeyPatch, *steps: Step | Exception) -> None:
    def ask(question: str) -> Iterator[Step]:
        for step in steps:
            if isinstance(step, Exception):
                raise step
            yield step

    monkeypatch.setattr(bootstrap, "ask", ask)


def events(body: str) -> list[tuple[str, dict[str, object]]]:
    pairs = []
    for block in body.strip().split("\n\n"):
        name_line, data_line = block.split("\n")
        name = name_line.removeprefix("event: ")
        data = json.loads(data_line.removeprefix("data: "))
        pairs.append((name, data))
    return pairs


def test_ask_streams_each_step_as_an_event(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ask(
        monkeypatch,
        ToolCall("search_pages", "Wolverine"),
        ToolReply("search_pages", "James Howlett (Earth-616)"),
        answer(),
    )

    response = client.post("/ask", json={"question": "Who is Wolverine?"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert events(response.text) == [
        ("call", {"tool": "search_pages", "argument": "Wolverine"}),
        ("reply", {"tool": "search_pages", "text": "James Howlett (Earth-616)"}),
        (
            "answer",
            {
                "text": "Wolverine's real name is James Howlett [1].",
                "sources": [
                    {
                        "title": "James Howlett (Earth-616)",
                        "url": "https://example.test/a",
                    }
                ],
                "model_calls": 5,
                "tool_calls": 4,
                "input_tokens": 8636,
                "output_tokens": 102,
                "seconds": 150.6,
            },
        ),
    ]


def test_ask_ends_the_stream_with_an_error_event_after_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ask(
        monkeypatch,
        ToolCall("search_pages", "Wolverine"),
        RateLimited(),
    )

    response = client.post("/ask", json={"question": "Who is Wolverine?"})

    assert response.status_code == 200
    assert events(response.text) == [
        ("call", {"tool": "search_pages", "argument": "Wolverine"}),
        (
            "error",
            {"message": "Mistral is rate limiting requests; try again in a minute."},
        ),
    ]


def test_ask_without_a_key_is_a_503_with_no_stream(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    response = client.post("/ask", json={"question": "Who is Wolverine?"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Set MISTRAL_API_KEY to ask questions."}
    assert response.headers["content-type"] == "application/json"


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_ask_rejects_an_empty_or_overlong_question(question: str) -> None:
    response = client.post("/ask", json={"question": question})

    assert response.status_code == 422
