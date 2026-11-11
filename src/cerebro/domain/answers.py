"""What an answer is built from and cites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """A page an answer can cite."""

    title: str
    url: str


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
