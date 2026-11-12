"""Check the judge against a person's hand labels."""

from dataclasses import dataclass

from cerebro.ports.evaluation import RunStore


@dataclass(frozen=True)
class AgreementReport:
    both_correct: int
    both_wrong: int
    judge_only: int  # the judge ruled correct, the label wrong
    labels_only: int  # the label ruled correct, the judge wrong
    disagreed: tuple[str, ...]  # question ids, in order

    @property
    def compared(self) -> int:
        return self.both_correct + self.both_wrong + self.judge_only + self.labels_only

    @property
    def agreement(self) -> float:
        return (self.both_correct + self.both_wrong) / self.compared

    @property
    def kappa(self) -> float | None:
        return cohens_kappa(
            self.both_correct, self.both_wrong, self.judge_only, self.labels_only
        )


def check_agreement(store: RunStore) -> AgreementReport:
    """Compare the judge's verdicts with the hand labels, over the questions that
    have both.
    """
    verdicts = store.verdicts()
    labels = store.labels()

    both_correct = 0
    both_wrong = 0
    judge_only = 0
    labels_only = 0
    disagreed: list[str] = []
    for question_id in sorted(verdicts.keys() & labels.keys()):
        judge_correct = verdicts[question_id].correct
        label_correct = labels[question_id].correct

        if judge_correct and label_correct:
            both_correct += 1
        elif not judge_correct and not label_correct:
            both_wrong += 1
        elif judge_correct:
            judge_only += 1
            disagreed.append(question_id)
        else:
            labels_only += 1
            disagreed.append(question_id)

    return AgreementReport(
        both_correct, both_wrong, judge_only, labels_only, tuple(disagreed)
    )


def cohens_kappa(
    both_correct: int, both_wrong: int, judge_only: int, labels_only: int
) -> float | None:
    """How much more the judge and the labels agree than two raters with their
    same rates of "correct" would by chance, from 1 for perfect agreement down
    through 0 for no better than chance.

    None when chance agreement is 1, which is when both put every question in the
    same class (or none were compared): there is nothing to measure against.
    """
    total = both_correct + both_wrong + judge_only + labels_only
    judge_correct = both_correct + judge_only
    labels_correct = both_correct + labels_only
    judge_wrong = both_wrong + labels_only
    labels_wrong = both_wrong + judge_only

    # Chance agreement is this count over total squared; integers keep "is it
    # exactly 1" free of rounding.
    chance_pairs = judge_correct * labels_correct + judge_wrong * labels_wrong
    if chance_pairs == total * total:
        return None

    observed = (both_correct + both_wrong) / total
    chance = chance_pairs / (total * total)

    return (observed - chance) / (1 - chance)
