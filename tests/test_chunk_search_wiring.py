"""Which passage search the agent gets, and that a replay needs no embedding server."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from eval_helpers import golden_line, golden_question
from pydantic import SecretStr

from cerebro import bootstrap
from cerebro.adapters.http_recording import RecordingTransport
from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.mistral import ministral
from cerebro.adapters.numpy_vectors import NumpyVectorStore
from cerebro.adapters.sqlite_chunks import SqliteChunkIndex
from cerebro.adapters.sqlite_records import SqliteRecordStore
from cerebro.application.evaluation import run_eval
from cerebro.domain.answers import Step
from cerebro.domain.chunks import Chunk
from cerebro.domain.evaluation import Exchange

# Three passages; a query about "weather" is a keyword match for the first only, and
# the embedding server places that query next to the second.
TEXTS = ["Ann Doe controls the weather.", "She stirs the clouds.", "She likes tea."]
VECTORS = [[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]]
QUERY_VECTOR = [0.0, 1.0]

OLLAMA_URL = "http://ollama.test:11434"


@pytest.fixture(autouse=True)
def stored(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Passages and their vectors in the data folder, and no search chosen."""
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    chunks = [
        Chunk(f"1:7:{n}", 1, 7, n, "Ann Doe (Earth-1)", "Powers", "", text)
        for n, text in enumerate(TEXTS)
    ]
    SqliteChunkIndex(data_dir / "records.sqlite").replace_chunks(chunks)
    store = NumpyVectorStore(data_dir / "embeddings" / "text")
    store.save_part(0, [chunk.id for chunk in chunks], VECTORS)


class Server:
    """Stands in for the embedding server and the model, and counts its requests."""

    def __init__(self) -> None:
        self.embeddings = 0
        self.chats = iter(
            [
                self.reply({"tool_calls": [self.search_call()]}),
                self.reply({"content": "Ann Doe controls the weather [1]."}),
            ]
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            self.embeddings += 1
            return httpx.Response(200, json={"embeddings": [QUERY_VECTOR]})

        return httpx.Response(200, json=next(self.chats))

    @staticmethod
    def search_call() -> dict[str, Any]:
        arguments = json.dumps({"query": "weather"})
        function = {"name": "search_text", "arguments": arguments}
        return {"id": "call0", "type": "function", "function": function}

    @staticmethod
    def reply(message: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "ministral-14b-2512",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "", **message},
                }
            ],
        }


def texts_found(search_transport: httpx.BaseTransport) -> list[str]:
    hits = bootstrap.chunk_search(search_transport).search("weather", limit=5)
    return [hit.chunk.text for hit in hits]


def test_without_an_ollama_server_the_agent_searches_by_keyword_alone() -> None:
    server = Server()

    found = texts_found(httpx.MockTransport(server))

    assert found == [TEXTS[0]]
    assert server.embeddings == 0


def test_with_an_ollama_server_the_agent_searches_by_keyword_and_meaning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", OLLAMA_URL)
    server = Server()

    found = texts_found(httpx.MockTransport(server))

    # The weather passage is a keyword hit, the clouds one a meaning hit, and the
    # tea one comes last: it is a lesser meaning hit and no keyword hit.
    assert found == [TEXTS[0], TEXTS[1], TEXTS[2]]
    assert server.embeddings == 1


def test_the_search_line_names_what_is_in_use(monkeypatch: pytest.MonkeyPatch) -> None:
    keyword_only = bootstrap.search_label()
    monkeypatch.setenv("OLLAMA_BASE_URL", OLLAMA_URL)
    both = bootstrap.search_label()

    assert "keyword only" in keyword_only
    assert "keyword and meaning" in both


# Replaying a run


@pytest.fixture
def golden(data_dir: Path) -> None:
    path = data_dir / "evals" / "golden.jsonl"
    path.parent.mkdir()
    path.write_text(json.dumps(golden_line("a")) + "\n", encoding="utf-8")


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        raise AssertionError("a replay must not send a request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


def record_run(data_dir: Path) -> JsonlRunStore:
    """A run of one question that searches the passages, as the agent does live."""
    server = Server()
    store = JsonlRunStore(data_dir / "runs" / "r")

    def ask(question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        recorder = RecordingTransport(httpx.MockTransport(server), exchanges)
        model = ministral(SecretStr("not-a-key"), recorder, paced=False)
        records = SqliteRecordStore(data_dir / "records.sqlite")
        agent = LangGraphAgent(model, records, bootstrap.chunk_search(recorder))
        return agent.steps(question)

    run_eval(ask, [golden_question("a")], store, model="ministral-14b")
    return store


def test_a_replay_serves_the_saved_query_vectors_and_never_calls_the_embedder(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    golden: None,
    no_network: None,
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", OLLAMA_URL)
    store = record_run(data_dir)
    models = [exchange["request"].get("model") for exchange in store.exchanges("a")]
    assert "nomic-embed-text" in models
    # The replay is run with the server unset, to show it needs no setting.
    monkeypatch.delenv("OLLAMA_BASE_URL")

    report = bootstrap.replay_run("r")

    assert (report.checked, report.mismatches) == (1, ())


def test_a_replay_of_a_keyword_run_stays_keyword_when_a_server_is_set(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    golden: None,
    no_network: None,
) -> None:
    record_run(data_dir)
    monkeypatch.setenv("OLLAMA_BASE_URL", OLLAMA_URL)

    report = bootstrap.replay_run("r")

    assert (report.checked, report.mismatches) == (1, ())
