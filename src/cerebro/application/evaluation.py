"""Answer the golden questions with one model and keep every result, then
rerun a kept run offline to check it reproduces.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, fields
from functools import partial
from itertools import zip_longest

from cerebro.domain.answers import Answer, Step, ToolCall, ToolReply
from cerebro.domain.evaluation import Exchange, Failure, GoldenQuestion, RunResult
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.evaluation import RunStore

# A question and a list of exchanges in, the agent's steps out. In a run the list
# starts empty and the model's exchanges are added to it as they happen; in a
# replay it holds the exchanges to answer from.
Ask = Callable[[str, list[Exchange]], Iterator[Step]]
# The same for a replay, with the name of the model that answered first.
Reask = Callable[[str, str, list[Exchange]], Iterator[Step]]
Progress = Callable[[RunResult], None]  # called as each question finishes


@dataclass(frozen=True)
class RunReport:
    answered: int
    failed: int
    skipped: int  # already answered by an earlier run


@dataclass(frozen=True)
class Mismatch:
    question_id: str
    difference: str  # the first thing that differs from the saved result


@dataclass(frozen=True)
class ReplayReport:
    checked: int
    mismatches: tuple[Mismatch, ...]


def run_eval(
    ask: Ask,
    questions: list[GoldenQuestion],
    store: RunStore,
    *,
    model: str,
    limit: int | None = None,
    progress: Progress | None = None,
) -> RunReport:
    """Answer every question that has no answer saved yet.

    A question the provider fails on is saved as a failure and the run goes on;
    a rerun tries it again, and the new result replaces the failure. Any other
    error, such as a missing key, stops the run: the results saved so far are
    kept. `limit` caps how many questions this run tries.
    """
    answered_before = store.answered_ids()
    todo = [q for q in questions if q.id not in answered_before]
    skipped = len(questions) - len(todo)
    if limit is not None:
        todo = todo[:limit]

    answered = 0
    failed = 0
    for question in todo:
        exchanges: list[Exchange] = []
        result = _answer(ask, question, model, exchanges)

        # Exchanges first: a result with no exchanges could not be replayed.
        store.save_exchanges(question.id, exchanges)
        store.append(result)

        if isinstance(result.final, Answer):
            answered += 1
        else:
            failed += 1

        if progress is not None:
            progress(result)

    return RunReport(answered=answered, failed=failed, skipped=skipped)


def replay_run(
    reask: Reask, questions: list[GoldenQuestion], store: RunStore
) -> ReplayReport:
    """Ask each answered question again from its saved exchanges and compare the
    steps and the answer with the saved result.

    The tools read the local records, so a rerun that changes nothing gives the
    saved steps and answer back. A question that is no longer in the golden set
    counts as a mismatch.
    """
    by_id = {question.id: question for question in questions}
    saved = [result for result in store.results() if isinstance(result.final, Answer)]

    mismatches: list[Mismatch] = []
    for result in saved:
        question = by_id.get(result.question_id)
        if question is None:
            mismatches.append(Mismatch(result.question_id, "not in the golden set"))
            continue

        # Any error ends the question, not only the provider's: a model library
        # may wrap the replay's refusal in an error of its own.
        replayed = _answer(
            partial(reask, result.model),
            question,
            result.model,
            store.exchanges(question.id),
            caught=(Exception,),
        )

        difference = _first_difference(result, replayed)
        if difference is not None:
            mismatches.append(Mismatch(question.id, difference))

    return ReplayReport(checked=len(saved), mismatches=tuple(mismatches))


def _first_difference(saved: RunResult, replayed: RunResult) -> str | None:
    # The steps come first: a changed tool reply shows up here, before the model
    # request that carries it fails to match its recording.
    for number, (was, now) in enumerate(
        zip_longest(saved.trace, replayed.trace), start=1
    ):
        if was != now:
            return f"step {number}: saved {was}, replayed {now}"

    assert isinstance(saved.final, Answer)
    if isinstance(replayed.final, Failure):
        failure = replayed.final
        return f"answer: saved an answer, replayed {failure.type}: {failure.message}"

    for field in fields(Answer):
        # The time an answer took differs on every run.
        if field.name == "seconds":
            continue

        was = getattr(saved.final, field.name)
        now = getattr(replayed.final, field.name)
        if was != now:
            return f"answer {field.name}: saved {was!r}, replayed {now!r}"

    return None


def _answer(
    ask: Ask,
    question: GoldenQuestion,
    model: str,
    exchanges: list[Exchange],
    caught: tuple[type[Exception], ...] = (RateLimited, ModelTimeout, ProviderError),
) -> RunResult:
    # Outside the try: an error in setting up, such as a missing key, is no result.
    steps = ask(question.question, exchanges)

    trace: list[ToolCall | ToolReply] = []
    final: Answer | Failure | None = None

    try:
        for step in steps:
            match step:
                case ToolCall():
                    trace.append(step)
                case ToolReply():
                    # A reply runs to thousands of characters; its first line says
                    # what it is.
                    first_line = step.text.partition("\n")[0]
                    trace.append(ToolReply(step.tool, first_line))
                case Answer():
                    final = step
    except caught as error:
        final = Failure(type(error).__name__, str(error))

    if final is None:
        final = Failure("NoAnswer", "The agent ended without an answer.")

    return RunResult(question.id, model, tuple(trace), final)
