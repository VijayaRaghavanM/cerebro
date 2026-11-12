"""Mistral's real replies, recorded once and replayed, checked against our adapter.

To re-record (a few minutes, spends API calls):
    CEREBRO_RECORD_MISTRAL=1 uv run pytest -m live tests/test_mistral_contract.py
"""

import json
import os
from pathlib import Path

import httpx
import pytest
from helpers import (
    FakeChunkSearch,
    FakeLookup,
    RecordingTransport,
    character,
    final_answer,
    replay,
)
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_mistralai import ChatMistralAI
from pydantic import SecretStr

from cerebro.adapters.langgraph_agent import LangGraphAgent
from cerebro.adapters.mistral import (
    MODEL,
    PACE,
    REQUESTS_PER_MINUTE,
    RETRIES,
    RETRY_WAIT_SECONDS,
    SECONDS_BETWEEN_REQUESTS,
    ministral,
    retrying_client,
)
from cerebro.domain.pages import Category
from cerebro.domain.records import PageHit
from cerebro.ports.agent import RateLimited
from cerebro.settings import Settings

FAKE_KEY = SecretStr("not-a-key")
RECORDINGS = Path(__file__).parent / "fixtures" / "mistral"
QUESTION = "What is Ann Doe's real name?"


def model_over(
    transport: httpx.BaseTransport,
    key: SecretStr = FAKE_KEY,
    rate_limiter: InMemoryRateLimiter | None = None,
) -> ChatMistralAI:
    # The key rides in the client's headers, which recordings never keep.
    client = httpx.Client(
        base_url="https://api.mistral.ai/v1",
        headers={"Authorization": f"Bearer {key.get_secret_value()}"},
        transport=transport,
    )
    return ChatMistralAI(
        model_name=MODEL,
        api_key=key,
        temperature=0,
        client=client,
        rate_limiter=rate_limiter,
    )


def ann_agent(model: ChatMistralAI) -> LangGraphAgent:
    ann = character(name="Anna Doe-Smith", current_alias="Ann Doe")
    hits = [PageHit(ann.title, Category.CHARACTERS, 5)]
    return LangGraphAgent(model, FakeLookup(hits, [ann]), FakeChunkSearch())


def test_a_recorded_answer_is_read_back() -> None:
    path = RECORDINGS / "answer.json"
    agent = ann_agent(model_over(replay(path)))

    answer = final_answer(agent, QUESTION)

    bodies = [e["response"]["body"] for e in json.loads(path.read_text("utf-8"))]
    usage = [body["usage"] for body in bodies]
    assert "[1]" in answer.text
    assert [source.title for source in answer.sources] == ["Ann Doe (Earth-1)"]
    assert answer.model_calls == len(bodies)
    assert answer.tool_calls == len(bodies) - 1
    assert answer.input_tokens == sum(u["prompt_tokens"] for u in usage)
    assert answer.output_tokens == sum(u["completion_tokens"] for u in usage)


def test_a_recorded_429_is_rate_limited() -> None:
    agent = ann_agent(model_over(replay(RECORDINGS / "rate_limited.json")))

    with pytest.raises(RateLimited):
        final_answer(agent, "Hi")


def refusing(
    times: int, then: httpx.BaseTransport, headers: dict[str, str] | None = None
) -> httpx.MockTransport:
    """Answers 429 to the first `times` requests, then passes them on."""
    recorded = json.loads((RECORDINGS / "rate_limited.json").read_text("utf-8"))
    refusal = recorded[0]["response"]["body"]
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if len(sent) <= times:
            return httpx.Response(429, json=refusal, headers=headers)
        return then.handle_request(request)

    return httpx.MockTransport(answer)


def retrying_model(inner: httpx.BaseTransport, waits: list[float]) -> ChatMistralAI:
    """A model with the client ministral() gives it, its waits kept in `waits`."""
    return ChatMistralAI(
        model_name=MODEL,
        api_key=FAKE_KEY,
        temperature=0,
        client=retrying_client(FAKE_KEY, inner, waits.append),
    )


def test_a_429_is_retried_after_a_pause() -> None:
    waits: list[float] = []
    inner = refusing(1, replay(RECORDINGS / "answer.json"))
    agent = ann_agent(retrying_model(inner, waits))

    answer = final_answer(agent, QUESTION)

    assert "[1]" in answer.text
    assert waits == [RETRY_WAIT_SECONDS]


def test_a_429_is_retried_a_limited_number_of_times() -> None:
    waits: list[float] = []
    inner = refusing(RETRIES + 5, replay(RECORDINGS / "answer.json"))
    agent = ann_agent(retrying_model(inner, waits))

    with pytest.raises(RateLimited):
        final_answer(agent, QUESTION)

    assert waits == [RETRY_WAIT_SECONDS] * RETRIES


def test_the_servers_retry_after_sets_the_pause() -> None:
    waits: list[float] = []
    inner = refusing(2, replay(RECORDINGS / "answer.json"), {"Retry-After": "7"})
    agent = ann_agent(retrying_model(inner, waits))

    final_answer(agent, QUESTION)

    assert waits == [7.0, 7.0]


def test_other_errors_are_not_retried() -> None:
    waits: list[float] = []
    inner = httpx.MockTransport(lambda request: httpx.Response(500))
    client = retrying_client(FAKE_KEY, inner, waits.append)

    response = client.post("/chat/completions", json={})

    assert response.status_code == 500
    assert waits == []


def test_models_share_one_rate_limiter() -> None:
    first = ministral(FAKE_KEY)
    second = ministral(FAKE_KEY)

    assert first.rate_limiter is not None
    assert first.rate_limiter is second.rate_limiter


def test_the_shared_pace_stays_under_the_account_limit() -> None:
    assert PACE.requests_per_second < REQUESTS_PER_MINUTE / 60


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("CEREBRO_RECORD_MISTRAL") != "1",
    reason="set CEREBRO_RECORD_MISTRAL=1 to record",
)
def test_record_mistral_exchanges() -> None:
    key = Settings().mistral_api_key
    if key is None:
        pytest.skip("MISTRAL_API_KEY is not set")

    # The same spacing the app uses, with its margin below the limit.
    pace = InMemoryRateLimiter(
        requests_per_second=1 / SECONDS_BETWEEN_REQUESTS, max_bucket_size=1
    )
    answering = RecordingTransport()
    final_answer(ann_agent(model_over(answering, key, pace)), QUESTION)
    answering.save(RECORDINGS / "answer.json")

    # No pacing here: back-to-back requests are how a 429 happens.
    flooding = RecordingTransport()
    agent = ann_agent(model_over(flooding, key))
    for _ in range(4):
        try:
            final_answer(agent, "Hi")
        except RateLimited:
            break
    assert flooding.exchanges[-1]["response"]["status"] == 429
    flooding.save(RECORDINGS / "rate_limited.json", last_only=True)
