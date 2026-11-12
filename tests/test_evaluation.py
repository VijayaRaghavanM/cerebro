from collections.abc import Iterator
from pathlib import Path

import pytest
from eval_helpers import answer, golden_question

from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.application.evaluation import run_eval
from cerebro.bootstrap import MissingKey
from cerebro.domain.answers import Step, ToolCall, ToolReply
from cerebro.domain.evaluation import Failure, RunResult
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited

QUESTIONS = [golden_question("a"), golden_question("b"), golden_question("c")]


# A fake agent: each question's script is the steps to yield, or an error to raise.
class Script:
    def __init__(self, **by_id: list[Step | Exception]) -> None:
        self.by_id = {f"Question {id}?": steps for id, steps in by_id.items()}
        self.asked: list[str] = []

    def __call__(self, question: str) -> Iterator[Step]:
        self.asked.append(question)
        for step in self.by_id.get(question, [answer()]):
            if isinstance(step, Exception):
                raise step
            yield step


def test_each_question_is_answered_and_saved(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path)
    ask = Script(
        a=[
            ToolCall("search_pages", "Wolverine"),
            ToolReply("search_pages", "James Howlett (Earth-616)\nmore\nlines"),
            answer("It is James."),
        ]
    )

    report = run_eval(ask, QUESTIONS, store, model="ministral-14b")

    assert (report.answered, report.failed, report.skipped) == (3, 0, 0)
    first = next(store.results())
    assert first == RunResult(
        "a",
        "ministral-14b",
        (
            ToolCall("search_pages", "Wolverine"),
            ToolReply("search_pages", "James Howlett (Earth-616)"),
        ),
        answer("It is James."),
    )


def test_a_provider_error_is_saved_for_that_question_and_the_run_goes_on(
    tmp_path: Path,
) -> None:
    store = JsonlRunStore(tmp_path)
    ask = Script(b=[ToolCall("read_page", "Thor"), RateLimited("slow down")])

    report = run_eval(ask, QUESTIONS, store, model="m")

    assert (report.answered, report.failed) == (2, 1)
    by_id = {result.question_id: result for result in store.results()}
    assert by_id["b"].final == Failure("RateLimited", "slow down")
    assert by_id["b"].trace == (ToolCall("read_page", "Thor"),)
    assert by_id["c"].final == answer()


@pytest.mark.parametrize("error", [ModelTimeout("late"), ProviderError("no")])
def test_every_provider_error_is_a_failure(tmp_path: Path, error: Exception) -> None:
    store = JsonlRunStore(tmp_path)

    report = run_eval(Script(a=[error]), QUESTIONS[:1], store, model="m")

    assert report.failed == 1
    assert next(store.results()).final == Failure(type(error).__name__, str(error))


def test_an_error_that_is_not_the_provider_s_stops_the_run(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path)
    ask = Script(b=[MissingKey("MISTRAL_API_KEY")])

    with pytest.raises(MissingKey):
        run_eval(ask, QUESTIONS, store, model="m")

    assert [result.question_id for result in store.results()] == ["a"]


def test_a_run_that_ends_without_an_answer_is_a_failure(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path)

    run_eval(Script(a=[ToolCall("read_page", "Thor")]), QUESTIONS[:1], store, model="m")

    final = next(store.results()).final
    assert isinstance(final, Failure)
    assert final.type == "NoAnswer"


def test_a_rerun_skips_answered_questions_and_tries_failed_ones_again(
    tmp_path: Path,
) -> None:
    first = Script(b=[ProviderError("no")])
    run_eval(first, QUESTIONS[:2], JsonlRunStore(tmp_path), model="m")

    second = Script(b=[answer("Second try.")])
    report = run_eval(second, QUESTIONS, JsonlRunStore(tmp_path), model="m")

    assert second.asked == ["Question b?", "Question c?"]
    assert (report.answered, report.failed, report.skipped) == (2, 0, 1)

    results = list(JsonlRunStore(tmp_path).results())
    assert [result.question_id for result in results] == ["a", "b", "c"]
    assert results[1].final == answer("Second try.")


def test_the_limit_caps_the_new_questions_not_the_saved_ones(tmp_path: Path) -> None:
    run_eval(Script(), QUESTIONS[:1], JsonlRunStore(tmp_path), model="m")

    ask = Script()
    report = run_eval(ask, QUESTIONS, JsonlRunStore(tmp_path), model="m", limit=1)

    assert ask.asked == ["Question b?"]
    assert (report.answered, report.skipped) == (1, 1)


def test_progress_is_reported_as_each_question_finishes(tmp_path: Path) -> None:
    seen: list[RunResult] = []

    run_eval(
        Script(b=[ProviderError("no")]),
        QUESTIONS,
        JsonlRunStore(tmp_path),
        model="m",
        progress=seen.append,
    )

    assert [result.question_id for result in seen] == ["a", "b", "c"]
