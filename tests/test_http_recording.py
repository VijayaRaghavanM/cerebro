import json

import httpx
import pytest

from cerebro.adapters.http_recording import (
    RecordingTransport,
    ReplayMismatch,
    ReplayTransport,
)
from cerebro.domain.evaluation import Exchange


def server(
    status: int = 200, headers: dict[str, str] | None = None
) -> httpx.MockTransport:
    """A server that answers every request with the number of requests so far."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={"n": len(seen)}, headers=headers)

    return httpx.MockTransport(answer)


def post(transport: httpx.BaseTransport, body: dict[str, str]) -> httpx.Response:
    client = httpx.Client(transport=transport, base_url="https://llm.test")
    return client.post(
        "/chat", json=body, headers={"Authorization": "Bearer sk-secret"}
    )


def test_a_recording_keeps_each_request_body_and_the_reply_status_and_body() -> None:
    recording = RecordingTransport(server())

    post(recording, {"q": "one"})
    post(recording, {"q": "two"})

    assert recording.exchanges == [
        {"request": {"q": "one"}, "response": {"status": 200, "body": {"n": 1}}},
        {"request": {"q": "two"}, "response": {"status": 200, "body": {"n": 2}}},
    ]


def test_a_recording_keeps_no_header() -> None:
    recording = RecordingTransport(server(headers={"x-ratelimit-limit": "2"}))

    post(recording, {"q": "one"})

    kept = json.dumps(recording.exchanges)
    assert "sk-secret" not in kept
    assert "Authorization" not in kept
    assert "ratelimit" not in kept


def test_the_caller_still_gets_the_reply_with_its_headers() -> None:
    recording = RecordingTransport(server(429, {"Retry-After": "7"}))

    response = post(recording, {"q": "one"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.json() == {"n": 1}


def test_a_recording_goes_into_the_list_it_is_given() -> None:
    kept: list[Exchange] = []

    post(RecordingTransport(server(), kept), {"q": "one"})

    assert len(kept) == 1


def test_a_replay_serves_the_recorded_replies_in_order() -> None:
    recording = RecordingTransport(server(500))
    post(recording, {"q": "one"})
    post(recording, {"q": "two"})
    replaying = ReplayTransport(recording.exchanges)

    first = post(replaying, {"q": "one"})
    second = post(replaying, {"q": "two"})

    assert (first.status_code, first.json()) == (500, {"n": 1})
    assert (second.status_code, second.json()) == (500, {"n": 2})


def test_a_replay_fails_on_a_request_that_differs_from_the_recording() -> None:
    recording = RecordingTransport(server())
    post(recording, {"q": "one"})
    replaying = ReplayTransport(recording.exchanges)

    with pytest.raises(ReplayMismatch, match="request 1 differs"):
        post(replaying, {"q": "other"})


def test_a_replay_waits_for_the_recorded_request_after_a_mismatch() -> None:
    recording = RecordingTransport(server())
    post(recording, {"q": "one"})
    replaying = ReplayTransport(recording.exchanges)

    with pytest.raises(ReplayMismatch):
        post(replaying, {"q": "other"})

    assert post(replaying, {"q": "one"}).json() == {"n": 1}


def test_a_replay_fails_when_the_recording_runs_out() -> None:
    recording = RecordingTransport(server())
    post(recording, {"q": "one"})
    replaying = ReplayTransport(recording.exchanges)
    post(replaying, {"q": "one"})

    with pytest.raises(ReplayMismatch, match="more requests than the 1 recorded"):
        post(replaying, {"q": "one"})


def test_a_replay_can_be_told_what_makes_two_requests_the_same() -> None:
    recording = RecordingTransport(server())
    post(recording, {"q": "one", "noise": "a"})
    only_q = ReplayTransport(
        recording.exchanges, same=lambda sent, recorded: sent["q"] == recorded["q"]
    )

    response = post(only_q, {"q": "one", "noise": "b"})

    assert response.json() == {"n": 1}
