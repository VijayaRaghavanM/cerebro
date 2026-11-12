import json
from pathlib import Path

import pytest

from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.application.agreement import (
    AgreementReport,
    check_agreement,
    cohens_kappa,
)
from cerebro.domain.evaluation import Verdict


def test_kappa_of_a_worked_example() -> None:
    # 50 questions: 20 both correct, 15 both wrong, 5 judge only, 10 labels only.
    # Observed agreement is 35 / 50 = 0.7. The judge says correct on 25 of 50 and
    # the labels on 30 of 50, so chance agreement is 0.5 * 0.6 + 0.5 * 0.4 = 0.5.
    # Kappa is (0.7 - 0.5) / (1 - 0.5) = 0.4.
    kappa = cohens_kappa(both_correct=20, both_wrong=15, judge_only=5, labels_only=10)

    assert kappa == pytest.approx(0.4)


def test_kappa_of_perfect_agreement_is_one() -> None:
    kappa = cohens_kappa(both_correct=6, both_wrong=4, judge_only=0, labels_only=0)

    assert kappa == pytest.approx(1.0)


def test_kappa_is_undefined_when_both_rule_every_question_the_same_way() -> None:
    assert (
        cohens_kappa(both_correct=9, both_wrong=0, judge_only=0, labels_only=0) is None
    )
    assert (
        cohens_kappa(both_correct=0, both_wrong=9, judge_only=0, labels_only=0) is None
    )


def test_kappa_is_undefined_when_nothing_was_compared() -> None:
    assert cohens_kappa(0, 0, 0, 0) is None


def test_the_four_counts_and_the_disagreements_come_from_the_questions_with_both(
    tmp_path: Path,
) -> None:
    store = JsonlRunStore(tmp_path)
    judge = {"a": True, "b": False, "c": True, "d": False, "e": True}
    labels = {"a": True, "b": False, "c": False, "d": True}  # none for e
    for question_id, correct in judge.items():
        store.save_verdict(question_id, Verdict(correct, "."))
    lines = [
        json.dumps({"question_id": question_id, "correct": correct, "reason": "."})
        for question_id, correct in labels.items()
    ]
    (tmp_path / "labels.jsonl").write_text("\n".join(lines) + "\n")

    report = check_agreement(store)

    assert report == AgreementReport(
        both_correct=1,
        both_wrong=1,
        judge_only=1,
        labels_only=1,
        disagreed=("c", "d"),
    )
    assert report.compared == 4
    assert report.agreement == 0.5
