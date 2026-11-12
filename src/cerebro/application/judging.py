"""Have a judge rule on the answers a run gave."""

from collections.abc import Callable
from dataclasses import dataclass

from cerebro.application.scoring import observed_outcome
from cerebro.domain.answers import Answer
from cerebro.domain.evaluation import Failure, GoldenQuestion, Outcome, Verdict
from cerebro.ports.evaluation import Judge, RunStore

Progress = Callable[[str, Verdict], None]  # called with each question's id and verdict


@dataclass(frozen=True)
class JudgeReport:
    judged: int
    correct: int  # of the judged
    skipped: int  # already judged by an earlier run


def judge_run(
    judge: Judge,
    questions: list[GoldenQuestion],
    store: RunStore,
    progress: Progress | None = None,
) -> JudgeReport:
    """Ask the judge about every answer that expects one and has no verdict yet,
    and keep each verdict as it comes.

    Only an answer to a question that expects an answer is judged. A refusal or a
    clarification is scored by rules, and so is a failure. An error from the judge
    stops the run: the verdicts kept so far stay, and a rerun goes on from there.
    """
    by_id = {question.id: question for question in questions}
    judged_before = store.verdicts()

    judged = 0
    correct = 0
    skipped = 0
    for result in store.results():
        question = by_id.get(result.question_id)
        if question is None or not _needs_judge(question, result.final):
            continue

        if question.id in judged_before:
            skipped += 1
            continue

        assert isinstance(result.final, Answer)
        verdict = judge.verdict(
            question.question, question.expected_facts, result.final.text
        )
        store.save_verdict(question.id, verdict)

        judged += 1
        correct += verdict.correct
        if progress is not None:
            progress(question.id, verdict)

    return JudgeReport(judged=judged, correct=correct, skipped=skipped)


def _needs_judge(question: GoldenQuestion, final: Answer | Failure) -> bool:
    if question.expected_outcome != Outcome.ANSWER:
        return False

    # A refusal or a clarification, where an answer was expected, is unsolved by rule.
    return (
        isinstance(final, Answer)
        and observed_outcome(question, final) == Outcome.ANSWER
    )
