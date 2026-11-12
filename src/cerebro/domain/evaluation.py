"""The golden questions and what a model did with them."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cerebro.domain.answers import Answer, ToolCall, ToolReply

# One request to the model and its reply, as JSON. Serving a question's exchanges
# back in order reruns its model calls with no network.
type Exchange = dict[str, Any]


class Split(StrEnum):
    """Which half of the golden set a question belongs to. The values are what
    `--split` accepts.
    """

    DEV = "dev"
    TEST = "test"


class Outcome(StrEnum):
    """What a response to a question is. A golden question expects one of the
    first three; FAILED is only ever observed.
    """

    ANSWER = "answer"
    REFUSE = "refuse"
    CLARIFY = "clarify"
    FAILED = "failed"


@dataclass(frozen=True)
class GoldenQuestion:
    """A question with what a good answer contains and where it comes from."""

    id: str
    split: Split
    category: str
    question: str
    expected_outcome: Outcome
    expected_facts: tuple[str, ...]
    expected_pages: tuple[str, ...]
    expected_tools: tuple[str, ...]
    source: str
    source_url: str
    license: str
    original: str | None = None  # the question as first written, if it was reworded
    source_author: str | None = None


@dataclass(frozen=True)
class Failure:
    """A run that ended on the model provider's error instead of an answer."""

    type: str
    message: str


@dataclass(frozen=True)
class Verdict:
    """A judge's ruling on whether an answer states the expected facts correctly."""

    correct: bool
    reason: str  # one sentence


@dataclass(frozen=True)
class RunResult:
    """What one model did with one golden question."""

    question_id: str
    model: str
    # The tool calls and replies in order. A reply keeps only its first line.
    trace: tuple[ToolCall | ToolReply, ...]
    final: Answer | Failure
