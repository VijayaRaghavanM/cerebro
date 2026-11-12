from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from eval_helpers import answer, golden_question

from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.application.evaluation import Mismatch, Reask, replay_run, run_eval
from cerebro.bootstrap import MissingSetting
from cerebro.domain.answers import Step, ToolCall, ToolReply
from cerebro.domain.evaluation import Exchange, Failure, GoldenQuestion, RunResult
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.evaluation import ExchangesMissing

QUESTIONS = [golden_question("a"), golden_question("b"), golden_question("c")]


# A fake agent: each question's script is the steps to yield, or an error to raise.
class Script:
    def __init__(self, **by_id: list[Step | Exception]) -> None:
        self.by_id = {f"Question {id}?": steps for id, steps in by_id.items()}
        self.asked: list[str] = []

    def __call__(self, question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        self.asked.append(question)
        exchanges.append({"request": question})
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


def test_each_questions_exchanges_are_saved_with_its_result(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path)
    ask = Script(b=[ProviderError("no")])

    run_eval(ask, QUESTIONS, store, model="m")

    # A failed question keeps its exchanges too, and each question only its own.
    assert store.exchanges("a") == [{"request": "Question a?"}]
    assert store.exchanges("b") == [{"request": "Question b?"}]
    assert store.exchanges("c") == [{"request": "Question c?"}]


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
    ask = Script(b=[MissingSetting("MISTRAL_API_KEY")])

    with pytest.raises(MissingSetting):
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


# Replaying a run


def steps(
    reply: str = "James Howlett (Earth-616)", text: str = "It is James."
) -> list[Step | Exception]:
    return [
        ToolCall("search_pages", "Wolverine"),
        ToolReply("search_pages", reply),
        answer(text),
    ]


def reasking(script: Script, models: list[str] | None = None) -> Reask:
    """A replay that runs the script, noting the model it was told to use."""

    def reask(model: str, question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        if models is not None:
            models.append(model)
        return script(question, exchanges)

    return reask


def saved_run(
    tmp_path: Path,
    questions: list[GoldenQuestion] = QUESTIONS[:1],
    **by_id: list[Step | Exception],
) -> JsonlRunStore:
    store = JsonlRunStore(tmp_path)
    run_eval(Script(**by_id), questions, store, model="ministral-14b")
    return store


def test_a_replay_that_changes_nothing_reproduces_every_answer(tmp_path: Path) -> None:
    store = saved_run(tmp_path, QUESTIONS, a=steps(), b=steps(), c=steps())
    models: list[str] = []

    report = replay_run(
        reasking(Script(a=steps(), b=steps(), c=steps()), models), QUESTIONS, store
    )

    assert (report.checked, report.mismatches) == (3, ())
    assert models == ["ministral-14b"] * 3


def test_a_replay_is_handed_the_exchanges_saved_for_that_question(
    tmp_path: Path,
) -> None:
    store = saved_run(tmp_path, QUESTIONS)
    store.save_exchanges("b", [{"request": "saved for b"}])
    given: dict[str, list[Exchange]] = {}

    def reask(model: str, question: str, exchanges: list[Exchange]) -> Iterator[Step]:
        given[question] = list(exchanges)
        return iter([answer()])

    replay_run(reask, QUESTIONS, store)

    assert given["Question b?"] == [{"request": "saved for b"}]
    assert given["Question a?"] == [{"request": "Question a?"}]


def test_the_time_an_answer_took_is_not_compared(tmp_path: Path) -> None:
    store = saved_run(tmp_path, a=steps())
    slower = replace(answer("It is James."), seconds=99.0)

    report = replay_run(
        reasking(Script(a=[*steps()[:2], slower])), QUESTIONS[:1], store
    )

    assert report.mismatches == ()


def test_a_changed_tool_reply_is_the_first_difference(tmp_path: Path) -> None:
    store = saved_run(tmp_path, a=steps())

    report = replay_run(
        reasking(Script(a=steps(reply="Logan (Earth-1)"))), QUESTIONS[:1], store
    )

    (mismatch,) = report.mismatches
    assert mismatch.question_id == "a"
    assert mismatch.difference == (
        "step 2: "
        "saved ToolReply(tool='search_pages', text='James Howlett (Earth-616)'), "
        "replayed ToolReply(tool='search_pages', text='Logan (Earth-1)')"
    )


def test_a_changed_answer_names_the_field_that_differs(tmp_path: Path) -> None:
    store = saved_run(tmp_path, a=steps())

    report = replay_run(
        reasking(Script(a=steps(text="It is Logan."))), QUESTIONS[:1], store
    )

    (mismatch,) = report.mismatches
    assert mismatch.difference == (
        "answer text: saved 'It is James.', replayed 'It is Logan.'"
    )


def test_a_replay_that_stops_short_differs_at_the_missing_step(tmp_path: Path) -> None:
    store = saved_run(tmp_path, a=steps())

    report = replay_run(
        reasking(Script(a=steps()[:1] + [answer("It is James.")])), QUESTIONS[:1], store
    )

    (mismatch,) = report.mismatches
    assert mismatch.difference.startswith("step 2: saved ToolReply(")
    assert mismatch.difference.endswith("replayed None")


def test_a_replay_that_fails_at_the_provider_is_a_mismatch(tmp_path: Path) -> None:
    store = saved_run(tmp_path, a=steps())

    report = replay_run(
        reasking(Script(a=[*steps()[:2], ProviderError("no")])), QUESTIONS[:1], store
    )

    (mismatch,) = report.mismatches
    assert mismatch.difference == (
        "answer: saved an answer, replayed ProviderError: no"
    )


def test_a_replay_that_raises_any_error_is_a_mismatch(tmp_path: Path) -> None:
    store = saved_run(tmp_path, a=steps())

    report = replay_run(
        reasking(Script(a=[*steps()[:2], RuntimeError("Connection error.")])),
        QUESTIONS[:1],
        store,
    )

    (mismatch,) = report.mismatches
    assert mismatch.difference == (
        "answer: saved an answer, replayed RuntimeError: Connection error."
    )


def test_only_answered_questions_are_replayed(tmp_path: Path) -> None:
    store = saved_run(tmp_path, QUESTIONS, b=[ProviderError("no")])
    script = Script()

    report = replay_run(reasking(script), QUESTIONS, store)

    assert script.asked == ["Question a?", "Question c?"]
    assert (report.checked, report.mismatches) == (2, ())


def test_a_question_gone_from_the_golden_set_is_a_mismatch(tmp_path: Path) -> None:
    store = saved_run(tmp_path, QUESTIONS)

    report = replay_run(reasking(Script()), QUESTIONS[:2], store)

    assert report.checked == 3
    assert report.mismatches == (Mismatch("c", "not in the golden set"),)


def test_a_run_saved_without_exchanges_cannot_be_replayed(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path)
    store.append(RunResult("a", "m", (), answer()))

    with pytest.raises(ExchangesMissing, match="a"):
        replay_run(reasking(Script()), QUESTIONS[:1], store)
