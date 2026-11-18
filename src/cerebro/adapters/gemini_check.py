"""An answer check by Gemini Flash, through Gemini's OpenAI-compatible endpoint."""

import json
import time
from collections.abc import Callable

import httpx
import openai
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import SecretStr

from cerebro.adapters.openai_chat import openai_chat
from cerebro.domain.answers import Check, CheckVerdict
from cerebro.ports.answer_check import AnswerChecker

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL = "gemini-3.8-flash"

PROMPT = (
    "You check an assistant's answer before a user sees it. The assistant answers "
    "questions about Marvel comics with tools. Below are the user's question, "
    "everything the tools returned, and the assistant's answer.\n"
    "\n"
    "Give one verdict:\n"
    '- "answers": every claim the answer depends on is stated in the tool output, '
    "and that output is about exactly what the question asks: the same character or "
    "team (the same reality: Earth-616 unless the question names another), the same "
    "comic, the same event.\n"
    '- "off_target": the claims are in the tool output, but the output is about '
    "something other than what the question asks: another reality's version, a "
    "different comic from the one the question means, or a step of the question that "
    "no tool output settles (for example, the question asks about the comic in which "
    "someone first appeared, and nothing shown says which comic that was).\n"
    '- "unsupported": a claim the answer depends on is not in the tool output, or the '
    "output contradicts it.\n"
    "\n"
    "Judge only against the tool output, not your own knowledge of Marvel comics.\n"
    'Reply with JSON only: {"verdict": "answers" | "off_target" | "unsupported", '
    '"missing": "one sentence on what the tool output lacks, or empty"}'
)

# A check takes about 4 seconds (20 recorded answers, 2026-11-13). These limits are
# multiples of that, not values tuned on evaluation results.
DEADLINE_SECONDS = 20
CALL_TIMEOUT_SECONDS = 15
RETRY_WAITS = (1, 3)
# Statuses that clear on their own. Any other, such as a wrong key, will not.
TEMPORARY_STATUSES = {408, 429, 500, 502, 503, 504}

UNCHECKED = Check(CheckVerdict.UNCHECKED)


class Breaker:
    """Stops checking for a while after several checks in a row could not run, so
    an outage makes the first few answers wait instead of every one.

    One breaker is shared by every checker in a process: a checker lasts one
    question, the outage does not.
    """

    def __init__(
        self,
        failures: int = 3,
        rest_seconds: float = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failures = failures
        self.rest_seconds = rest_seconds
        self.clock = clock
        self.in_a_row = 0
        self.resting_until = 0.0

    def resting(self) -> bool:
        return self.clock() < self.resting_until

    def record(self, ran: bool) -> None:
        if ran:
            self.in_a_row = 0
            return

        self.in_a_row += 1
        if self.in_a_row >= self.failures:
            self.resting_until = self.clock() + self.rest_seconds
            self.in_a_row = 0


class GeminiAnswerChecker(AnswerChecker):
    """Asks Gemini Flash for a verdict, sending through `transport` if given, so a
    run can record the check and a replay can serve it back."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        breaker: Breaker,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # The SDK does not retry: the tries here share one deadline.
        model = openai_chat(
            GEMINI_URL,
            MODEL,
            api_key=api_key,
            transport=transport,
            timeout=CALL_TIMEOUT_SECONDS,
            max_retries=0,
        )
        self.model = model.bind(response_format={"type": "json_object"})
        self.breaker = breaker
        self.clock = clock
        self.sleep = sleep

    def check(self, question: str, evidence: str, answer: str) -> Check:
        if self.breaker.resting():
            return UNCHECKED

        result = self._ask(question, evidence, answer)
        self.breaker.record(result.verdict is not CheckVerdict.UNCHECKED)
        return result

    def _ask(self, question: str, evidence: str, answer: str) -> Check:
        request = [
            SystemMessage(PROMPT),
            HumanMessage(
                f"QUESTION:\n{question}\n\nTOOL OUTPUT:\n{evidence}\n\n"
                f"ANSWER:\n{answer}"
            ),
        ]
        deadline = self.clock() + DEADLINE_SECONDS

        for wait in (*RETRY_WAITS, None):
            remaining = deadline - self.clock()
            if remaining <= 0:
                break

            try:
                reply = self.model.invoke(
                    request, timeout=min(CALL_TIMEOUT_SECONDS, remaining)
                )
                return _check(reply.text)
            except openai.APIStatusError as error:
                if error.status_code not in TEMPORARY_STATUSES:
                    break
            except (openai.APIConnectionError, httpx.HTTPError):
                pass
            except (AttributeError, IndexError):
                # A reply with no message, which LangChain cannot read; the next
                # try usually has one.
                pass

            if wait is None or self.clock() + wait >= deadline:
                break
            self.sleep(wait)

        return UNCHECKED


def _check(text: str) -> Check:
    """The verdict in a reply. A reply that holds none means the check did not
    run, so the answer goes out unchecked rather than being held back."""
    try:
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
        verdict = CheckVerdict(str(data.get("verdict", "")))
    except (ValueError, AttributeError):
        return UNCHECKED

    if verdict is CheckVerdict.UNCHECKED:
        return UNCHECKED
    return Check(verdict, str(data.get("missing", "")))
