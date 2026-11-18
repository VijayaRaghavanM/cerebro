"""What an answer is built from and cites."""

from dataclasses import dataclass
from enum import StrEnum

from cerebro.domain.comicvine import ComicVineCharacter


@dataclass(frozen=True)
class Source:
    """A page an answer can cite."""

    title: str
    url: str


# A source titled this way is the Comic Vine record of a page the answer also reads.
_COMIC_VINE = "Comic Vine: "


def comic_vine_source(character: ComicVineCharacter) -> Source:
    """The source for a character's Comic Vine record."""
    return Source(f"{_COMIC_VINE}{character.name}", character.url)


def is_comic_vine(source: Source) -> bool:
    return source.title.startswith(_COMIC_VINE)


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


# What the agent says when the records lack the answer: the agent writes it and
# scoring reads it.
REFUSAL = "I couldn't find that in the records."


class CheckVerdict(StrEnum):
    """What a check of an answer against the tool output it came from found. The
    values are what a run's trace shows."""

    ANSWERS = "answers"
    # The claims are in the tool output, but it is about something the question
    # did not ask: another reality's version, another comic, an unsettled step.
    OFF_TARGET = "off_target"
    # A claim is missing from the tool output, or the output contradicts it.
    UNSUPPORTED = "unsupported"
    # The check could not run, so the answer goes out as it was.
    UNCHECKED = "unchecked"


@dataclass(frozen=True)
class Check:
    """A check's verdict, and what the tool output lacks when it found a problem."""

    verdict: CheckVerdict
    missing: str = ""


type Step = ToolCall | ToolReply | Answer
