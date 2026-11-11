"""The agent: a question in, a cited answer out."""

from abc import ABC, abstractmethod

from cerebro.domain.answers import Answer


class RateLimited(Exception):
    """The model provider refused the request for too many requests."""


class ModelTimeout(Exception):
    """The model provider did not reply in time."""


class ProviderError(Exception):
    """The model provider failed in any other way."""


class Agent(ABC):
    """Answers a question from the stored records."""

    @abstractmethod
    def answer(self, question: str) -> Answer:
        """The answer to `question`, with the pages it cites.

        Raises RateLimited, ModelTimeout or ProviderError if the model fails.
        """
