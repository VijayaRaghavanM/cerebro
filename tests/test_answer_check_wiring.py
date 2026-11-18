import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from eval_helpers import golden_line, golden_question
from pydantic import SecretStr

from cerebro import bootstrap
from cerebro.adapters.gemini_check import MODEL as CHECK_MODEL
from cerebro.adapters.gemini_check import Breaker, GeminiAnswerChecker
from cerebro.adapters.http_recording import RecordingTransport
from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.mistral import ministral
from cerebro.adapters.sqlite_chunks import SqliteChunkIndex
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application.evaluation import run_eval
from cerebro.domain.answers import Step, ToolCall
from cerebro.domain.chunks import Chunk
from cerebro.domain.evaluation import Exchange


@pytest.fixture(autouse=True)
def stored(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One passage, one golden question, keyword search and no Gemini key."""
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    chunk = Chunk("1:7:0", 1, 7, 0, "Ann Doe (Earth-1)", "Powers", "", "She flies.")
    SqliteChunkIndex(data_dir / "records.sqlite").replace_chunks([chunk])
    golden = data_dir / "evals" / "golden.jsonl"
    golden.parent.mkdir()
    golden.write_text(json.dumps(golden_line("a")) + "\n", encoding="utf-8")


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        raise AssertionError("a replay must not send a request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


class Server:
    """Stands in for the model, which searches once and answers, and for Gemini,
    which passes the answer."""

    def __init__(self) -> None:
        search = {"name": "search_text", "arguments": json.dumps({"query": "flies"})}
        self.chats: Iterator[dict[str, Any]] = iter(
            [
                {"tool_calls": [{"id": "c0", "type": "function", "function": search}]},
                {"content": "Ann Doe flies [1]."},
            ]
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        message: dict[str, Any]
        if json.loads(request.content)["model"] == CHECK_MODEL:
            message = {"content": '{"verdict": "answers", "missing": ""}'}
        else:
            message = next(self.chats)
        return httpx.Response(200, json=completion(message))


def completion(message: dict[str, Any]) -> dict[str, Any]:
    full = {"role": "assistant", "content": "", **message}
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "ministral-14b-2512",
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        "choices": [{"index": 0, "finish_reason": "stop", "message": full}],
    }


def record_run(data_dir: Path, *, checked: bool) -> JsonlRunStore:
    """A run of one question, as `cerebro eval run` makes it, with or without the
    answer check."""
    server = Server()
    store = JsonlRunStore(data_dir / "runs" / "r")

    def ask(question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        recorder = RecordingTransport(httpx.MockTransport(server), exchanges)
        model = ministral(SecretStr("not-a-key"), recorder, paced=False)
        checker = None
        if checked:
            checker = GeminiAnswerChecker(
                SecretStr("not-a-key"), breaker=Breaker(), transport=recorder
            )
        records = SqliteRecordStore(data_dir / "records.sqlite")
        agent = LangGraphAgent(
            model, records, bootstrap.chunk_search(recorder), checker
        )
        return agent.steps(question)

    run_eval(ask, [golden_question("a")], store, model="ministral-14b")
    return store


def test_the_check_line_says_whether_answers_are_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    off = bootstrap.check_label()
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-key")
    on = bootstrap.check_label()

    assert "off" in off
    assert "GEMINI_API_KEY" in off
    assert "checked" in on


def test_a_replay_serves_the_saved_check_without_a_key_or_the_network(
    data_dir: Path, no_network: None
) -> None:
    store = record_run(data_dir, checked=True)
    (result,) = store.results()
    assert ToolCall("check_answer", "answers") in result.trace

    report = bootstrap.replay_run("r")

    assert (report.checked, report.mismatches) == (1, ())


def test_a_replay_of_an_unchecked_run_stays_unchecked_when_a_key_is_set(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch, no_network: None
) -> None:
    record_run(data_dir, checked=False)
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-key")

    report = bootstrap.replay_run("r")

    assert (report.checked, report.mismatches) == (1, ())


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> Server:
    """Every request goes to the fake server instead of the network, so the run
    is built the way `cerebro eval run` builds it."""
    server = Server()

    def handle(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        request.read()
        return server(request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")
    return server


def eval_trace() -> tuple[Step, ...]:
    bootstrap.run_eval(bootstrap.Contestant.MINISTRAL_14B_OPENROUTER, run_name="r")
    (result,) = JsonlRunStore(Path("runs") / "r").results()
    return result.trace


def test_with_a_gemini_key_a_run_checks_its_answers(
    served: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-key")

    trace = eval_trace()

    assert ToolCall("check_answer", "answers") in trace


def test_without_a_gemini_key_a_run_answers_unchecked(served: Server) -> None:
    trace = eval_trace()

    assert not any(
        isinstance(step, ToolCall) and step.tool == "check_answer" for step in trace
    )
