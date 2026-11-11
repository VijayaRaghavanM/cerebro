"""Turning text into vectors."""

from abc import ABC, abstractmethod


class EmbedderUnavailable(Exception):
    """The embedding server could not be reached or failed."""


class Embedder(ABC):
    """Embeds text so that similar meanings land close together."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, each normalised to length 1.

        Length 1 means a dot product between two vectors is their cosine.
        Raises EmbedderUnavailable if the server fails.
        """

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """The vector for a search question, normalised to length 1.

        Raises EmbedderUnavailable if the server fails.
        """


class VectorStore(ABC):
    """Keeps vectors in numbered parts, so a long run can stop and resume."""

    @abstractmethod
    def has_part(self, number: int) -> bool:
        """Whether part `number` was saved in full."""

    @abstractmethod
    def save_part(
        self, number: int, chunk_ids: list[str], vectors: list[list[float]]
    ) -> None:
        """Keep one vector per chunk id as part `number`.

        The part counts as saved only once all of it is written.
        """
