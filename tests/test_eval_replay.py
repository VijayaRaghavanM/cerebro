"""A run's model exchanges are kept, and replaying them reproduces the run."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
from eval_helpers import golden_question
from helpers import FakeChunkSearch, FakeLookup, character
from pydantic import SecretStr

from cerebro.adapters.http_recording import RecordingTransport, ReplayTransport
from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.mistral import ministral
from cerebro.application.evaluation import ReplayReport, replay_run, run_eval
from cerebro.domain.answers import Answer, Step
from cerebro.domain.evaluation import Exchange
from cerebro.domain.pages import Category
from cerebro.domain.records import PageHit

KEY = SecretStr("not-a-key")
TITLE = "Ann Doe (Earth-1)"
QUESTIONS = [golden_question("a"), golden_question("b")]


def completion(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "ministral-14b-2512",
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
    }


def calling(name: str, key: str, argument: str) -> dict[str, Any]:
    call = {
        "id": "call0",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps({key: argument})},
    }
    return completion({"role": "assistant", "content": "", "tool_calls": [call]})


def saying(text: str) -> dict[str, Any]:
    return completion({"role": "assistant", "content": text})


def server() -> httpx.MockTransport:
    """A model that searches, reads the page, then answers, for any question."""
    replies = iter(
        [
            calling("search_pages", "name", "Ann Doe"),
            calling("read_page", "title", TITLE),
            saying("Her name is Ann Doe [1]."),
        ]
    )
    return httpx.MockTransport(lambda request: httpx.Response(200, json=next(replies)))


def agent_over(transport: httpx.BaseTransport, appearances: int) -> LangGraphAgent:
    """The real agent and model, over this transport and a made-up wiki."""
    hits = [PageHit(TITLE, Category.CHARACTERS, appearances)]
    lookup = FakeLookup(hits, [character(name="Ann Doe")])
    model = ministral(KEY, transport, paced=False)

    return LangGraphAgent(model, lookup, FakeChunkSearch())


def recorded_run(tmp_path: Path, appearances: int = 5) -> JsonlRunStore:
    store = JsonlRunStore(tmp_path)

    def ask(question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        transport = RecordingTransport(server(), exchanges)
        return agent_over(transport, appearances).steps(question)

    run_eval(ask, QUESTIONS, store, model="ministral-14b")
    return store


def replayed(store: JsonlRunStore, appearances: int = 5) -> ReplayReport:
    def reask(model: str, question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        return agent_over(ReplayTransport(exchanges), appearances).steps(question)

    return replay_run(reask, QUESTIONS, store)


def test_a_run_keeps_every_model_exchange_of_each_question(tmp_path: Path) -> None:
    store = recorded_run(tmp_path)

    for question in QUESTIONS:
        exchanges = store.exchanges(question.id)
        assert len(exchanges) == 3
        assert exchanges[0]["request"]["messages"][-1]["content"] == question.question
        assert exchanges[2]["response"]["body"]["choices"][0]["message"]["content"] == (
            "Her name is Ann Doe [1]."
        )


def test_the_kept_exchanges_hold_no_key(tmp_path: Path) -> None:
    recorded_run(tmp_path)

    for file in (tmp_path / "exchanges").iterdir():
        assert KEY.get_secret_value() not in file.read_text(encoding="utf-8")


def test_replaying_a_run_reproduces_its_steps_and_answers_offline(
    tmp_path: Path,
) -> None:
    store = recorded_run(tmp_path)
    saved = [result.final for result in store.results()]
    assert all(isinstance(final, Answer) for final in saved)

    report = replayed(store)

    assert (report.checked, report.mismatches) == (2, ())


def test_a_changed_tool_result_is_reported_at_the_step_that_changed(
    tmp_path: Path,
) -> None:
    store = recorded_run(tmp_path, appearances=5)

    report = replayed(store, appearances=9)

    assert [m.question_id for m in report.mismatches] == ["a", "b"]
    assert report.mismatches[0].difference.startswith("step 2: saved ToolReply(")
    assert "in 5 comics" in report.mismatches[0].difference
    assert "in 9 comics" in report.mismatches[0].difference
