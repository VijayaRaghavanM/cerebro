"""A second look at an answer before the user sees it."""

from abc import ABC, abstractmethod

from cerebro.domain.answers import Check


class AnswerChecker(ABC):
    """Checks an answer against the question and the tool output it came from."""

    @abstractmethod
    def check(self, question: str, evidence: str, answer: str) -> Check:
        """The verdict on `answer`, given everything the tools returned.

        Never raises: when the check cannot run, the verdict is UNCHECKED.
        """
