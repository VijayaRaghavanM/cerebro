"""Answer the golden questions with one model and keep every result."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from cerebro.domain.answers import Answer, Step, ToolCall, ToolReply
from cerebro.domain.evaluation import Failure, GoldenQuestion, RunResult
from cerebro.ports.agent import ModelTimeout, ProviderError, RateLimited
from cerebro.ports.evaluation import RunStore

Ask = Callable[[str], Iterator[Step]]  # a question in, the agent's steps out
Progress = Callable[[RunResult], None]  # called as each question finishes


@dataclass(frozen=True)
class RunReport:
    answered: int
    failed: int
    skipped: int  # already answered by an earlier run


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
        result = _answer(ask, question, model)
        store.append(result)

        if isinstance(result.final, Answer):
            answered += 1
        else:
            failed += 1

        if progress is not None:
            progress(result)

    return RunReport(answered=answered, failed=failed, skipped=skipped)


def _answer(ask: Ask, question: GoldenQuestion, model: str) -> RunResult:
    trace: list[ToolCall | ToolReply] = []
    final: Answer | Failure | None = None

    try:
        for step in ask(question.question):
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
    except (RateLimited, ModelTimeout, ProviderError) as error:
        final = Failure(type(error).__name__, str(error))

    if final is None:
        final = Failure("NoAnswer", "The agent ended without an answer.")

    return RunResult(question.id, model, tuple(trace), final)
