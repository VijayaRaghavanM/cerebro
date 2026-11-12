from dataclasses import replace
from pathlib import Path

import pytest
from eval_helpers import answer, golden_question

from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.application.judging import JudgeReport, judge_run
from cerebro.domain.answers import REFUSAL, Answer
from cerebro.domain.evaluation import Failure, Outcome, RunResult, Verdict
from cerebro.ports.agent import RateLimited
from cerebro.ports.evaluation import Judge

CORRECT = Verdict(True, "States the fact.")
WRONG = Verdict(False, "Names someone else.")


class FakeJudge(Judge):
    """Rules from a list of verdicts, then raises RateLimited, and keeps the
    answers it was asked about.
    """

    def __init__(self, *verdicts: Verdict) -> None:
        self.verdicts = list(verdicts)
        self.asked: list[str] = []

    def verdict(
        self, question: str, expected_answer_facts: tuple[str, ...], answer_text: str
    ) -> Verdict:
        self.asked.append(answer_text)
        if not self.verdicts:
            raise RateLimited("slow down")

        return self.verdicts.pop(0)


def kept(tmp_path: Path, *results: RunResult) -> JsonlRunStore:
    store = JsonlRunStore(tmp_path)
    for result in results:
        store.append(result)

    return store


def result(id: str, final: Answer | Failure) -> RunResult:
    return RunResult(id, "m", (), final)


def test_each_answer_is_judged_and_its_verdict_kept(tmp_path: Path) -> None:
    store = kept(
        tmp_path,
        result("a", answer("First [1].")),
        result("b", answer("Second [1].")),
    )
    judge = FakeJudge(CORRECT, WRONG)
    told: list[tuple[str, Verdict]] = []

    report = judge_run(
        judge,
        [golden_question("a"), golden_question("b")],
        store,
        lambda id, verdict: told.append((id, verdict)),
    )

    assert report == JudgeReport(judged=2, correct=1, skipped=0)
    assert judge.asked == ["First [1].", "Second [1]."]
    assert told == [("a", CORRECT), ("b", WRONG)]
    assert JsonlRunStore(tmp_path).verdicts() == {"a": CORRECT, "b": WRONG}


def test_a_rerun_skips_the_answers_already_judged(tmp_path: Path) -> None:
    store = kept(tmp_path, result("a", answer()), result("b", answer()))
    questions = [golden_question("a"), golden_question("b")]
    judge_run(FakeJudge(CORRECT, CORRECT), questions, store)

    judge = FakeJudge()
    report = judge_run(judge, questions, store)

    assert report == JudgeReport(judged=0, correct=0, skipped=2)
    assert judge.asked == []


def test_a_judge_that_fails_midway_keeps_its_verdicts_and_a_rerun_goes_on(
    tmp_path: Path,
) -> None:
    store = kept(tmp_path, result("a", answer()), result("b", answer()))
    questions = [golden_question("a"), golden_question("b")]

    with pytest.raises(RateLimited):
        judge_run(FakeJudge(CORRECT), questions, store)

    assert JsonlRunStore(tmp_path).verdicts() == {"a": CORRECT}
    judge = FakeJudge(WRONG)
    report = judge_run(judge, questions, JsonlRunStore(tmp_path))
    assert report == JudgeReport(judged=1, correct=0, skipped=1)
    assert len(judge.asked) == 1


def test_refusals_clarifications_and_failures_are_not_judged(tmp_path: Path) -> None:
    refusal = replace(answer(REFUSAL), sources=())
    store = kept(
        tmp_path,
        result("refused", refusal),
        result("asked", answer("Which one do you mean?")),
        result("failed", Failure("RateLimited", "")),
        result("answered", answer()),
    )
    questions = [
        golden_question(id) for id in ("refused", "asked", "failed", "answered")
    ]
    judge = FakeJudge(CORRECT)

    report = judge_run(judge, questions, store)

    assert report.judged == 1
    assert judge.asked == ["James Howlett [1]."]


def test_a_comparison_answer_naming_both_expected_pages_is_judged(
    tmp_path: Path,
) -> None:
    text = "Thor Odinson outweighs Steven Rogers [1]."
    store = kept(tmp_path, result("a", answer(text)))
    question = replace(
        golden_question("a"),
        expected_pages=("Thor Odinson (Earth-616)", "Steven Rogers (Earth-616)"),
    )
    judge = FakeJudge(CORRECT)

    report = judge_run(judge, [question], store)

    assert report.judged == 1
    assert judge.asked == [text]


def test_a_question_that_expects_a_refusal_is_not_judged(tmp_path: Path) -> None:
    store = kept(tmp_path, result("a", answer("Somebody [1].")))
    question = replace(
        golden_question("a"), expected_outcome=Outcome.REFUSE, expected_facts=()
    )
    judge = FakeJudge()

    report = judge_run(judge, [question], store)

    assert report.judged == 0
    assert judge.asked == []


def test_a_result_no_longer_in_the_golden_set_is_not_judged(tmp_path: Path) -> None:
    store = kept(tmp_path, result("gone", answer()))
    judge = FakeJudge()

    assert judge_run(judge, [golden_question("a")], store).judged == 0
    assert judge.asked == []
