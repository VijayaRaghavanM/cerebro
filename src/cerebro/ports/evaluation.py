"""The golden questions to read and the results of a run to keep."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from cerebro.domain.evaluation import GoldenQuestion, RunResult, Split


class GoldenSet(ABC):
    """The questions a model is measured on."""

    @abstractmethod
    def questions(self, split: Split | None) -> list[GoldenQuestion]:
        """The questions in one split, or in both when `split` is None."""


class RunStore(ABC):
    """The results of one run, kept as each question finishes."""

    @abstractmethod
    def answered_ids(self) -> set[str]:
        """The ids of the questions whose latest result is an answer."""

    @abstractmethod
    def append(self, result: RunResult) -> None:
        """Keep a result without touching the ones already kept."""

    @abstractmethod
    def results(self) -> Iterator[RunResult]:
        """One result per question, the latest kept, in the order the questions
        were first kept.
        """
