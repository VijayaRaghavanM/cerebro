"""The golden questions to read and the results of a run to keep."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from cerebro.domain.evaluation import Exchange, GoldenQuestion, RunResult, Split


class ExchangesMissing(Exception):
    """A question's model exchanges were not kept. The message is its id."""


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

    @abstractmethod
    def save_exchanges(self, question_id: str, exchanges: list[Exchange]) -> None:
        """Keep the model exchanges that answered a question, replacing any kept
        for it before.
        """

    @abstractmethod
    def exchanges(self, question_id: str) -> list[Exchange]:
        """The exchanges kept for a question. Raises ExchangesMissing if none are."""
