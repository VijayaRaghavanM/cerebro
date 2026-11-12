from typing import Any

import httpx2
import openai
import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from cerebro.adapters.llm_judge import RESPONSE_FORMAT, LlmJudge
from cerebro.domain.evaluation import Verdict
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.evaluation import VerdictUnreadable


class FakeChat(BaseChatModel):
    """Replies with fixed text, or raises, and keeps what it was sent."""

    reply: str = ""
    error: Exception | None = None
    sent: list[list[BaseMessage]] = []
    options: list[dict[str, Any]] = []

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.sent.append(messages)
        self.options.append(kwargs)
        if self.error is not None:
            raise self.error

        return ChatResult(generations=[ChatGeneration(message=AIMessage(self.reply))])

    @property
    def _llm_type(self) -> str:
        return "fake"


def judge_of(
    reply: str = "", error: Exception | None = None
) -> tuple[LlmJudge, FakeChat]:
    model = FakeChat(reply=reply, error=error, sent=[], options=[])
    return LlmJudge(model), model


def ask(judge: LlmJudge) -> Verdict:
    return judge.verdict(
        "Who created Kitty Pryde?",
        ("Chris Claremont", "John Byrne"),
        "Chris Claremont and John Byrne created her [1].",
    )


def test_a_structured_reply_becomes_a_verdict() -> None:
    judge, _ = judge_of('{"reason": "Both creators are named.", "correct": true}')

    assert ask(judge) == Verdict(correct=True, reason="Both creators are named.")


def test_the_judge_is_asked_with_the_facts_the_answer_and_a_schema() -> None:
    judge, model = judge_of('{"reason": "r", "correct": false}')

    ask(judge)

    request = model.sent[0][1].text
    assert "Who created Kitty Pryde?" in request
    assert "- Chris Claremont\n- John Byrne" in request
    assert "Chris Claremont and John Byrne created her [1]." in request
    assert model.options[0]["response_format"] == RESPONSE_FORMAT


@pytest.mark.parametrize(
    "reply",
    [
        "Yes, it is correct.",
        '{"reason": "r"}',
        '{"reason": "r", "correct": "yes"}',
        '{"reason": 3, "correct": true}',
        '{"reason": "r", "correct": true, "extra": 1}',
        '["r", true]',
    ],
)
def test_a_reply_that_is_not_a_verdict_is_an_error_that_shows_the_reply(
    reply: str,
) -> None:
    judge, _ = judge_of(reply)

    with pytest.raises(VerdictUnreadable, match="judge"):
        ask(judge)


# The OpenAI SDK builds its errors from httpx2, its own copy of httpx.
def sdk_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://example.test/v1/chat/completions")


def test_the_sdks_errors_are_the_ports_errors() -> None:
    response = httpx2.Response(429, request=sdk_request())
    limited = openai.RateLimitError("slow down", response=response, body=None)
    timed_out = openai.APITimeoutError(sdk_request())
    server_error = openai.APIStatusError(
        "boom", response=httpx2.Response(500, request=sdk_request()), body=None
    )

    with pytest.raises(RateLimited):
        ask(judge_of(error=limited)[0])
    with pytest.raises(ModelTimeout):
        ask(judge_of(error=timed_out)[0])
    with pytest.raises(ProviderError, match="HTTP 500"):
        ask(judge_of(error=server_error)[0])
