"""The agent: a question in, a cited answer out."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from cerebro.domain.answers import Step


class RateLimited(Exception):
    """The model provider refused the request for too many requests."""


class ModelTimeout(Exception):
    """The model provider did not reply in time."""


class ProviderError(Exception):
    """The model provider failed in any other way."""


class Agent(ABC):
    """Answers a question from the stored records."""

    @abstractmethod
    def steps(self, question: str) -> Iterator[Step]:
        """Each tool call and its reply as they happen, then the answer last.

        Raises RateLimited, ModelTimeout or ProviderError if the model fails.
        """
