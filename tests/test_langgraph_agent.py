from collections.abc import Iterator, Sequence
from typing import Any

import httpx
import pytest
from helpers import FakeLookup, character, detail, final_answer, vine
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

from cerebro.adapters.langgraph_agent import (
    GAVE_UP,
    MAX_TOOL_CALLS,
    SYSTEM_PROMPT,
    LangGraphAgent,
)
from cerebro.domain.answers import Answer, Source, ToolCall, ToolReply
from cerebro.domain.pages import Category
from cerebro.domain.records import PageHit
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited

TITLE = "Ann Doe (Earth-1)"


class ScriptedModel(GenericFakeChatModel):
    """Replays AI messages, and records what each call was sent."""

    seen: list[list[BaseMessage]] = []

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen.append(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)


class FailingModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    error: Exception

    @property
    def _llm_type(self) -> str:
        return "failing"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FailingModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise self.error


def scripted(*replies: AIMessage) -> ScriptedModel:
    messages: Iterator[AIMessage] = iter(replies)
    return ScriptedModel(messages=messages, seen=[])


def call(name: str, argument: str, tokens: tuple[int, int] = (10, 2)) -> AIMessage:
    key = "name" if name == "search_pages" else "title"
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": {key: argument}, "id": f"id{argument}"}],
        usage_metadata={
            "input_tokens": tokens[0],
            "output_tokens": tokens[1],
            "total_tokens": sum(tokens),
        },
    )


def reply(text: str, tokens: tuple[int, int] = (30, 5)) -> AIMessage:
    return AIMessage(
        content=text,
        usage_metadata={
            "input_tokens": tokens[0],
            "output_tokens": tokens[1],
            "total_tokens": sum(tokens),
        },
    )


def lookup(matched: bool = False) -> FakeLookup:
    hits = [PageHit(TITLE, Category.CHARACTERS, 5)]
    ann = character(name="Ann Doe")
    comicvine = vine(detail(issues=())) if matched else None
    return FakeLookup(hits, [ann], comicvine)


def ask(model: BaseChatModel, matched: bool = False) -> Any:
    return final_answer(LangGraphAgent(model, lookup(matched)), "Who is Ann Doe?")


def test_a_search_a_read_and_a_cited_reply_make_an_answer() -> None:
    model = scripted(
        call("search_pages", "ann"),
        call("read_page", TITLE, (20, 3)),
        reply("Ann Doe controls the weather [1]."),
    )

    answer = ask(model)

    assert answer.text == "Ann Doe controls the weather [1]."
    assert answer.sources == (Source(TITLE, "https://wiki.example/Ann_Doe_(Earth-1)"),)
    assert answer.model_calls == 3
    assert answer.tool_calls == 2
    assert answer.input_tokens == 10 + 20 + 30
    assert answer.output_tokens == 2 + 3 + 5
    assert answer.seconds > 0


def test_steps_show_each_call_and_reply_in_order_then_the_answer() -> None:
    model = scripted(
        call("search_pages", "ann"),
        call("read_page", TITLE),
        reply("Ann Doe controls the weather [1]."),
    )

    steps = list(LangGraphAgent(model, lookup()).steps("Who is Ann Doe?"))

    search, found, read, page, final = steps
    assert search == ToolCall("search_pages", "ann")
    assert isinstance(found, ToolReply)
    assert found.tool == "search_pages"
    assert TITLE in found.text
    assert read == ToolCall("read_page", TITLE)
    assert isinstance(page, ToolReply)
    assert page.tool == "read_page"
    assert page.text.endswith(f"Sources: [1] {TITLE}")
    assert isinstance(final, Answer)
    assert final.text == "Ann Doe controls the weather [1]."


def test_a_run_stopped_by_the_cap_still_ends_with_the_gave_up_answer() -> None:
    loop = [call("search_pages", f"ann{n}") for n in range(MAX_TOOL_CALLS + 5)]

    steps = list(LangGraphAgent(scripted(*loop), lookup()).steps("Who?"))

    final = steps[-1]
    assert isinstance(final, Answer)
    assert final.text == GAVE_UP
    # Each call that ran has its reply; the last call is the one the cap stopped.
    expected = [ToolCall, ToolReply] * MAX_TOOL_CALLS + [ToolCall]
    assert [type(step) for step in steps[:-1]] == expected


def test_the_model_is_given_the_system_prompt() -> None:
    model = scripted(reply("Hello."))

    ask(model)

    assert model.seen[0][0].content == SYSTEM_PROMPT


def test_a_read_lists_its_numbered_sources_for_the_model() -> None:
    model = scripted(call("read_page", TITLE), reply("Done [1]."))

    ask(model, matched=True)

    tool_text = model.seen[1][-1].content
    assert isinstance(tool_text, str)
    assert tool_text.endswith(f"Sources: [1] {TITLE}, [2] Comic Vine: Weather Witch")


def test_a_citation_names_only_the_source_it_numbers() -> None:
    model = scripted(call("read_page", TITLE), reply("Her real name is Ann [2]."))

    answer = ask(model, matched=True)

    # The one source cited becomes [1], so the text matches the list printed under it.
    assert answer.text == "Her real name is Ann [1]."
    assert answer.sources == (
        Source("Comic Vine: Weather Witch", "https://vine.example/5"),
    )


def test_sources_are_listed_in_citation_order_once_each() -> None:
    model = scripted(call("read_page", TITLE), reply("B [2], A [1], B again [2]."))

    answer = ask(model, matched=True)

    assert answer.text == "B [1], A [2], B again [1]."
    assert [s.title for s in answer.sources] == [
        "Comic Vine: Weather Witch",
        TITLE,
    ]


def test_numbers_continue_across_reads_and_repeat_for_the_same_page() -> None:
    model = scripted(
        call("read_page", TITLE),
        call("read_page", TITLE),
        reply("Done [1]."),
    )

    ask(model, matched=True)

    first = model.seen[1][-1].content
    second = model.seen[2][-1].content
    assert isinstance(first, str) and isinstance(second, str)
    assert first.endswith(
        "Sources: [1] Ann Doe (Earth-1), [2] Comic Vine: Weather Witch"
    )
    assert second.endswith(first[first.index("Sources:") :])


def test_a_second_page_is_numbered_after_the_first() -> None:
    other = character(name="Bob Roe")
    other = type(other)(**{**other.__dict__, "pageid": 2, "title": "Bob Roe (Earth-1)"})
    both = FakeLookup([], [character(name="Ann Doe"), other])
    model = scripted(
        call("read_page", TITLE),
        call("read_page", "Bob Roe (Earth-1)"),
        reply("Both [1] [2]."),
    )

    answer = final_answer(LangGraphAgent(model, both), "Who?")

    assert [s.title for s in answer.sources] == [TITLE, "Bob Roe (Earth-1)"]


def test_a_marker_with_no_source_cites_nothing_and_shows_as_unknown() -> None:
    model = scripted(call("read_page", TITLE), reply("Made up [7]."))

    answer = ask(model)

    assert answer.text == "Made up [?]."
    assert answer.sources == ()


def test_an_answer_without_markers_cites_nothing() -> None:
    model = scripted(call("read_page", TITLE), reply("I couldn't find that."))

    assert ask(model).sources == ()


def test_the_step_cap_stops_a_looping_model() -> None:
    loop = [call("search_pages", f"ann{n}") for n in range(MAX_TOOL_CALLS + 5)]
    model = scripted(*loop)

    answer = ask(model)

    assert answer.text == GAVE_UP
    assert answer.sources == ()
    assert answer.tool_calls == MAX_TOOL_CALLS


def status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://model.example")
    return httpx.HTTPStatusError(
        "failed", request=request, response=httpx.Response(code, request=request)
    )


def test_http_429_is_rate_limited() -> None:
    with pytest.raises(RateLimited):
        ask(FailingModel(error=status_error(429)))


def test_a_timeout_is_a_model_timeout() -> None:
    with pytest.raises(ModelTimeout):
        ask(FailingModel(error=httpx.ReadTimeout("slow")))


@pytest.mark.parametrize(
    "error", [status_error(500), httpx.ConnectError("down")], ids=["500", "connect"]
)
def test_other_provider_failures_are_provider_errors(error: Exception) -> None:
    with pytest.raises(ProviderError):
        ask(FailingModel(error=error))


def test_tools_are_named_for_the_model() -> None:
    tools: list[BaseTool] = LangGraphAgent(scripted(), lookup())._tools({})

    assert [t.name for t in tools] == ["search_pages", "read_page"]
