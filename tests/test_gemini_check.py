import json
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import SecretStr

from cerebro.adapters.gemini_check import (
    MODEL,
    Breaker,
    GeminiAnswerChecker,
)
from cerebro.domain.answers import Check, CheckVerdict

UNCHECKED = Check(CheckVerdict.UNCHECKED)


class Clock:
    """Time that moves only when the code waits, or when a fake call takes long."""

    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


Reply = Callable[[httpx.Request], httpx.Response]


class Gemini:
    """Stands in for Gemini: gives the replies it was handed, the last one again
    once they run out, and keeps every request."""

    def __init__(self, *replies: Reply) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return reply(request)


def verdict(text: str) -> Reply:
    message = {"role": "assistant", "content": text}
    return lambda request: httpx.Response(200, json=completion(message))


def no_message(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=completion(None))


def status(code: int) -> Reply:
    return lambda request: httpx.Response(code, json={"error": {"message": "no"}})


def completion(message: dict[str, Any] | None) -> dict[str, Any]:
    choice = {"index": 0, "finish_reason": "stop", "message": message}
    return {"id": "x", "object": "chat.completion", "created": 0, "model": MODEL,
            "choices": [choice]}  # fmt: skip


ANSWERS = verdict('{"verdict": "answers", "missing": ""}')


def checker(
    gemini: Gemini, clock: Clock, breaker: Breaker | None = None
) -> GeminiAnswerChecker:
    return GeminiAnswerChecker(
        SecretStr("not-a-key"),
        breaker=breaker or Breaker(clock=clock),
        transport=httpx.MockTransport(gemini),
        clock=clock,
        sleep=clock.sleep,
    )


def test_the_check_sends_the_question_the_tool_output_and_the_answer() -> None:
    gemini = Gemini(ANSWERS)

    result = checker(gemini, Clock()).check("Who?", "tool said X", "X [1].")

    assert result == Check(CheckVerdict.ANSWERS)
    sent = gemini.requests[0]
    assert sent["model"] == MODEL
    assert sent["messages"][1]["content"] == (
        "QUESTION:\nWho?\n\nTOOL OUTPUT:\ntool said X\n\nANSWER:\nX [1]."
    )


def test_a_problem_comes_back_with_what_is_missing() -> None:
    gemini = Gemini(verdict('{"verdict": "unsupported", "missing": "No inker."}'))

    result = checker(gemini, Clock()).check("Who inked it?", "...", "Joe [1].")

    assert result == Check(CheckVerdict.UNSUPPORTED, "No inker.")


def test_a_wrong_key_gives_up_at_once() -> None:
    gemini, clock = Gemini(status(401)), Clock()

    result = checker(gemini, clock).check("Who?", "...", "X [1].")

    assert result == UNCHECKED
    assert len(gemini.requests) == 1
    assert clock.waits == []


def test_a_rate_limit_is_tried_again_after_a_short_wait() -> None:
    gemini, clock = Gemini(status(429), ANSWERS), Clock()

    result = checker(gemini, clock).check("Who?", "...", "X [1].")

    assert result == Check(CheckVerdict.ANSWERS)
    assert clock.waits == [1]


def test_a_reply_with_no_message_is_tried_again() -> None:
    gemini = Gemini(no_message, ANSWERS)

    result = checker(gemini, Clock()).check("Who?", "...", "X [1].")

    assert result == Check(CheckVerdict.ANSWERS)
    assert len(gemini.requests) == 2


def test_no_try_starts_after_the_deadline() -> None:
    clock = Clock()

    def slow(request: httpx.Request) -> httpx.Response:
        clock.now += 15
        raise httpx.ReadTimeout("slow", request=request)

    gemini = Gemini(slow)

    result = checker(gemini, clock).check("Who?", "...", "X [1].")

    assert result == UNCHECKED
    # Tried at 0 s and, after a 1 s wait, at 16 s; a third try would start past 20 s,
    # so there is no second wait.
    assert len(gemini.requests) == 2
    assert clock.waits == [1]


def test_a_reply_that_holds_no_verdict_lets_the_answer_out_unchecked() -> None:
    gemini = Gemini(verdict("Looks fine to me."))

    result = checker(gemini, Clock()).check("Who?", "...", "X [1].")

    assert result == UNCHECKED
    assert len(gemini.requests) == 1


def test_after_three_failed_checks_in_a_row_the_check_rests() -> None:
    gemini, clock = Gemini(status(401)), Clock()
    breaker = Breaker(clock=clock)
    check = checker(gemini, clock, breaker)

    for _ in range(3):
        check.check("Who?", "...", "X [1].")
    resting = check.check("Who?", "...", "X [1].")
    clock.now += 300
    rested = check.check("Who?", "...", "X [1].")

    assert resting == rested == UNCHECKED
    assert len(gemini.requests) == 4


def test_a_check_that_runs_starts_the_count_again() -> None:
    gemini, clock = Gemini(status(401), status(401), ANSWERS, status(401)), Clock()
    check = checker(gemini, clock)

    results = [check.check("Who?", "...", "X [1].") for _ in range(5)]

    assert results[2] == Check(CheckVerdict.ANSWERS)
    assert len(gemini.requests) == 5
