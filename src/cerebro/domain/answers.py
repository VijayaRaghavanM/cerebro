"""What an answer is built from and cites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """A page an answer can cite."""

    title: str
    url: str


@dataclass(frozen=True)
class ToolCall:
    """The agent calling a tool. Each tool takes one string: a name to search for
    or a title to read.
    """

    tool: str
    argument: str


@dataclass(frozen=True)
class ToolReply:
    """What a tool sent back: the text the model reads, with its source labels."""

    tool: str
    text: str


@dataclass(frozen=True)
class Answer:
    """An answer, the sources it cites, and what it cost to get."""

    text: str
    sources: tuple[Source, ...]
    model_calls: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    seconds: float


type Step = ToolCall | ToolReply | Answer
